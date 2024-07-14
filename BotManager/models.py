from django.db import models

# Create your models here.
# Create your models here.
class BotLogs(models.Model):
    description = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.description +"  " + str(self.created.strftime('%d-%B-%Y %H:%M:%S'))
class BotOrders(models.Model):
    order_id =  models.CharField(max_length=200)
    order_details = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_id +"  " +self.order_details +"  " + str(self.created.strftime('%d-%B-%Y %H:%M:%S'))

class BotSignals(models.Model):
    coinpair=models.CharField(max_length=50)
    side=models.CharField(max_length=50)
    price = models.CharField(max_length=50)
    sl = models.CharField(max_length=50)
    tp = models.CharField(max_length=50)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.price +"  " +self.sl +"  " +"  " +self.tp + str(self.created.strftime('%d-%B-%Y %H:%M:%S'))

class StaticData(models.Model):
    crypto = models.CharField(max_length=100)
    volume = models.IntegerField(default=1)
    leverage = models.IntegerField(default=11)
    static_id=models.IntegerField(default=1)
    created = models.DateTimeField(auto_now_add=True)