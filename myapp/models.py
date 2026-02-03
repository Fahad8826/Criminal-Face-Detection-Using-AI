from django.db import models

from django.db import models

class Criminal(models.Model):
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    crime_type = models.CharField(max_length=100)
    place = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='criminals/')
    label = models.IntegerField(unique=True)

    def __str__(self):
        return self.name
