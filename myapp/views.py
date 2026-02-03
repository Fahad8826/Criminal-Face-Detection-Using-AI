from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Criminal
from .face_utils import TRAINER_PATH, train_model, recognize_face

import os
import shutil
from django.conf import settings


# ================= HELPER FUNCTIONS =================

def sync_dataset_with_database():
    """
    Complete synchronization: rebuild dataset from scratch based on current database
    """
    # 1. DELETE OLD DATASET
    dataset_path = os.path.join(settings.MEDIA_ROOT, "dataset")
    if os.path.exists(dataset_path):
        shutil.rmtree(dataset_path)
    
    # 2. DELETE OLD TRAINER
    if os.path.exists(TRAINER_PATH):
        os.remove(TRAINER_PATH)
    
    # 3. RECREATE DATASET FROM DATABASE
    criminals = Criminal.objects.all()
    
    for criminal in criminals:
        label_dir = os.path.join(settings.MEDIA_ROOT, "dataset", str(criminal.label))
        os.makedirs(label_dir, exist_ok=True)
        
        # Copy the criminal's photo to dataset
        img_path = os.path.join(label_dir, "img1.jpg")
        
        # Copy from uploaded photo
        if os.path.exists(criminal.photo.path):
            shutil.copy(criminal.photo.path, img_path)
    
    # 4. RETRAIN MODEL
    if criminals.exists():
        train_model()


# ================= AUTH =================

def welcome(request):
    return render(request, "welcome.html")


def signup_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return render(request, "signup.html")
        
        User.objects.create_user(username=username, password=password)
        messages.success(request, "Account created successfully! Please login.")
        return redirect('login')
    
    return render(request, "signup.html")


def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )
        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password")
    
    return render(request, "login.html")


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully")
    return redirect('welcome')


# ================= DASHBOARD =================

@login_required
def dashboard_view(request):
    criminals = Criminal.objects.all().order_by('-id')
    return render(request, "dashboard/dashboard.html", {
        "criminals": criminals
    })


@login_required
def add_criminal(request):
    if request.method == "POST":
        try:
            # Determine next label
            last_criminal = Criminal.objects.order_by('-label').first()
            next_label = last_criminal.label + 1 if last_criminal else 1
            
            # Create criminal record
            criminal = Criminal.objects.create(
                name=request.POST['name'],
                age=request.POST['age'],
                crime_type=request.POST['crime_type'],
                place=request.POST['place'],
                label=next_label,
                photo=request.FILES['photo']
            )

            # Create dataset directory for this criminal
            label_dir = os.path.join(settings.MEDIA_ROOT, "dataset", str(criminal.label))
            os.makedirs(label_dir, exist_ok=True)

            # Save photo to dataset
            img_path = os.path.join(label_dir, "img1.jpg")
            with open(img_path, "wb+") as f:
                for chunk in criminal.photo.chunks():
                    f.write(chunk)

            # Retrain model with new data
            train_model()
            
            messages.success(request, f"Criminal '{criminal.name}' added successfully!")
            return redirect('dashboard')
        
        except Exception as e:
            messages.error(request, f"Error adding criminal: {str(e)}")
            return render(request, "dashboard/add_criminal.html")

    return render(request, "dashboard/add_criminal.html")


@login_required
def edit_criminal(request, id):
    criminal = get_object_or_404(Criminal, id=id)

    if request.method == "POST":
        try:
            # Update basic fields
            criminal.name = request.POST['name']
            criminal.age = request.POST['age']
            criminal.crime_type = request.POST['crime_type']
            criminal.place = request.POST['place']
            
            # Check if photo was updated
            photo_updated = False
            if 'photo' in request.FILES and request.FILES['photo']:
                criminal.photo = request.FILES['photo']
                photo_updated = True
                
                # Update dataset folder
                label_dir = os.path.join(settings.MEDIA_ROOT, "dataset", str(criminal.label))
                os.makedirs(label_dir, exist_ok=True)
                
                img_path = os.path.join(label_dir, "img1.jpg")
                with open(img_path, "wb+") as f:
                    for chunk in criminal.photo.chunks():
                        f.write(chunk)
            
            criminal.save()
            
            # Retrain model only if photo was updated
            if photo_updated:
                train_model()
                messages.success(request, f"Criminal '{criminal.name}' updated and model retrained!")
            else:
                messages.success(request, f"Criminal '{criminal.name}' updated successfully!")
            
            return redirect('dashboard')
        
        except Exception as e:
            messages.error(request, f"Error updating criminal: {str(e)}")

    return render(request, "dashboard/edit_criminal.html", {"criminal": criminal})


@login_required
def delete_criminal(request, id):
    criminal = get_object_or_404(Criminal, id=id)

    if request.method == "POST":
        try:
            criminal_name = criminal.name
            
            # Delete dataset folder for this criminal
            label_dir = os.path.join(settings.MEDIA_ROOT, "dataset", str(criminal.label))
            if os.path.exists(label_dir):
                shutil.rmtree(label_dir)
            
            # Delete the criminal record
            criminal.delete()
            
            # Retrain model without this criminal
            train_model()
            
            messages.success(request, f"Criminal '{criminal_name}' deleted and model retrained!")
            return redirect('dashboard')
        
        except Exception as e:
            messages.error(request, f"Error deleting criminal: {str(e)}")
            return redirect('dashboard')

    return render(request, "dashboard/delete_criminal.html", {
        "criminal": criminal
    })


@login_required
def search_criminal(request):
    criminal = None
    confidence = None
    searched = False

    if request.method == "POST":
        searched = True
        
        try:
            uploaded = request.FILES['photo']
            temp_path = os.path.join(settings.MEDIA_ROOT, "temp.jpg")

            # Save uploaded image temporarily
            with open(temp_path, "wb+") as f:
                for chunk in uploaded.chunks():
                    f.write(chunk)

            # Recognize face
            label, confidence = recognize_face(temp_path)
            
            # Debug logging
            print(f"🔍 Searching for label: {label}")
            print(f"📊 All labels in DB: {list(Criminal.objects.values_list('label', flat=True))}")

            # Search for criminal in database
            if label not in (None, "no_face"):
                criminal = Criminal.objects.filter(label=label).first()
                
                if criminal:
                    print(f"✅ Found: {criminal.name}")
                    messages.success(request, f"Criminal identified: {criminal.name}")
                else:
                    print(f"❌ No criminal found with label={label}")
                    messages.warning(request, "Face detected but no matching criminal in database")
            elif label == "no_face":
                messages.error(request, "No face detected in the uploaded image")
            else:
                messages.error(request, "Face recognition model not trained or confidence too low")
            
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        except Exception as e:
            messages.error(request, f"Error during search: {str(e)}")

    return render(request, "dashboard/search.html", {
        "criminal": criminal,
        "confidence": confidence,
        "searched": searched
    })


@login_required
def rebuild_dataset(request):
    """
    Rebuild the entire dataset from current database
    Use this if dataset and database get out of sync
    """
    try:
        # Get count before rebuild
        criminal_count = Criminal.objects.count()
        
        if criminal_count == 0:
            messages.warning(request, "No criminals in database to rebuild from")
            return redirect('dashboard')
        
        # Perform full sync
        sync_dataset_with_database()
        
        # Get labels after rebuild
        labels = list(Criminal.objects.values_list('label', flat=True))
        
        messages.success(request, f"Successfully rebuilt dataset for {criminal_count} criminal(s)")
        
        return render(request, "rebuild_result.html", {
            "success": True,
            "message": f"Successfully rebuilt dataset for {criminal_count} criminal(s)",
            "labels": labels
        })
    
    except Exception as e:
        messages.error(request, f"Error rebuilding dataset: {str(e)}")
        return render(request, "rebuild_result.html", {
            "success": False,
            "message": f"Error: {str(e)}"
        })


@login_required
def cleanup_orphaned_folders(request):
    """
    Remove dataset folders that don't have corresponding database records
    """
    try:
        dataset_path = os.path.join(settings.MEDIA_ROOT, "dataset")
        
        if not os.path.exists(dataset_path):
            messages.info(request, "No dataset folder found")
            return redirect('dashboard')
        
        # Get all labels from database
        db_labels = set(Criminal.objects.values_list('label', flat=True))
        
        # Get all folders in dataset
        removed_count = 0
        for folder_name in os.listdir(dataset_path):
            folder_path = os.path.join(dataset_path, folder_name)
            
            if os.path.isdir(folder_path):
                try:
                    folder_label = int(folder_name)
                    
                    # If this label doesn't exist in DB, remove it
                    if folder_label not in db_labels:
                        shutil.rmtree(folder_path)
                        removed_count += 1
                        print(f"🗑️ Removed orphaned folder: {folder_name}")
                
                except ValueError:
                    # Skip non-numeric folder names
                    pass
        
        if removed_count > 0:
            # Retrain after cleanup
            train_model()
            messages.success(request, f"Removed {removed_count} orphaned folder(s) and retrained model")
        else:
            messages.info(request, "No orphaned folders found. Dataset is clean!")
        
        return redirect('dashboard')
    
    except Exception as e:
        messages.error(request, f"Error during cleanup: {str(e)}")
        return redirect('dashboard')