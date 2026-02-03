from django.contrib import admin
from django.urls import path
from myapp import views   # 👈 import your app views

urlpatterns = [
   
    path('', views.welcome, name='welcome'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('add/', views.add_criminal, name='add_criminal'),
    path('search/', views.search_criminal, name='search_criminal'),

    path('edit/<int:id>/', views.edit_criminal, name='edit_criminal'),
    path('delete/<int:id>/', views.delete_criminal, name='delete_criminal'),

    path('rebuild-dataset/', views.rebuild_dataset, name='rebuild_dataset'),
]
