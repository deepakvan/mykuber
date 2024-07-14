from . import views
from django.urls import path

urlpatterns = [
    path('', views.home),
]


import threading
from .views import bot,database_Clenear
threading.Thread(target=bot).start()
threading.Thread(target=database_Clenear).start()
