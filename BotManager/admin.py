from django.contrib import admin
from .models import BotLogs, BotOrders,BotSignals,StaticData
# Register your models here.
admin.site.register(BotLogs)
admin.site.register(BotOrders)
admin.site.register(BotSignals)
admin.site.register(StaticData)