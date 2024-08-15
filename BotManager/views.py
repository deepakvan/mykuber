import os

from django.http import HttpResponse
from django.shortcuts import render
from . import models

import datetime
import time
from time import sleep
from . import algobot_helper_functions as hf
from binance.um_futures import UMFutures
from binance.error import ClientError
import pandas as pd
import threading
import random

from datetime import timedelta
from django.utils import timezone

# Create your views here.
def home(request):
    return HttpResponse("I'm Alive")


def bot():
    """ kuber """
    API_KEY = os.environ.get("API_KEY")
    API_SECRET = os.environ.get("API_SECRET")
    client=UMFutures(key=API_KEY,secret=API_SECRET)
    coinpair_list= ['ANKRUSDT']

    orders = 0
    symbol = ''

    threading.Thread(target=hf.remove_pending_orders_repeated, args=(client,)).start()
    while True:
        try:
            minutes = datetime.datetime.now().minute
            seconds = datetime.datetime.now().second
            if minutes % 15 <= 1 and seconds>=5: #minutes%15<=1
                # we need to get balance to check if the connection is good, or you have all the needed permissions
                balance = hf.get_balance_usdt(client)
                sleep(1)
                if balance == None:
                    print('Cant connect to API. Check IP, restrictions or wait some time')
                    models.BotLogs(description="----Cant connect to API. Check IP, restrictions or wait some time").save()
                if balance != None:
                    print("My balance is: ", balance, " USDT")
                    models.BotLogs(description="My balance is: "+ str(balance)+ " USDT").save()
                    # getting position list:
                    pos = hf.get_pos(client)
                    print(f'You have {len(pos)} opened positions:\n{pos}')
                    models.BotLogs(description=f'You have {len(pos)} opened positions:\n{pos}').save()
                    #if len(pos)==0:
                    ord = hf.check_orders(client)
                    #print("working")
                    #print(ord)
                    # removing stop orders for closed positions
                    for elem in ord:
                        if (not elem['symbol'] in pos):  # and (elem['type'] not in ['MARKET','LIMIT']):
                            hf.close_open_orders(client,elem)
                    if models.StaticData.objects.exists():
                        obj = models.StaticData.objects.get(static_id=1)
                        coinpair_list = [x.upper().strip() for x in str(obj.crypto).split(",")] #[obj.crypto]
                    print(coinpair_list)
                    random.shuffle(coinpair_list)
                    signal_list=[]
                    for coinpair in coinpair_list:
                        if not coinpair in pos:
                            df=hf.fetch_historical_data(client,coinpair,'15m',15)
                            #print(coinpair)
                            signal_data=hf.get_signal(df)
                            prev_day = hf.fetch_historical_data(client,coinpair,'1d',5)
                            prev_day = prev_day.iloc[-2,:]
                            if signal_data[1]['side']=='sell':
                                if prev_day['close'] < signal_data[1]["BUY_PRICE"]:
                                    signal_data = None
                            #break
                            if signal_data!=None:
                                #print([coinpair,signal_data])
                                signal_list.append([coinpair,signal_data])
                    for sig in signal_list:
                        print(sig)
                        models.BotSignals(coinpair=sig[0],side=str(sig[1]["side"]),price=str(sig[1]["BUY_PRICE"])
                                          ,sl=str(sig[1]["SL"]),tp=str(sig[1]["TP"])).save()
                        models.BotLogs(description=f'signal  {sig} ').save()
                    print("calling monitor")
                    models.BotLogs(description="calling monitor").save()
                    #hf.monitor_signal(client,signal_list,coinpair_list)
                    threading.Thread(target=hf.monitor_signal, args=(client,signal_list,coinpair_list)).start()

                #break # break while loop if needed
                time.sleep(3*60)
            elif minutes % 15 > 1:
                if (14 - (minutes % 15)) * 60 > 0:
                    print("sleeping for ", (14 - (minutes % 15)) * 60, " seconds (", 14 - (minutes % 15), ") minutes")
                    models.BotLogs(description=f'sleeping for  {(14 - (minutes % 15)) * 60} seconds:{14 - (minutes % 15)}').save()
                    time.sleep((14 - (minutes % 15)) * 60)
                    print("awaked at ",datetime.datetime.now())
                    models.BotLogs(description=f'----awaked at {datetime.datetime.now()}').save()
            time.sleep(5)
        except:
            print("Error in code Main Code")
            models.BotLogs(description=f'Error in Main code').save()

            pass

def database_Clenear():
    print("database cleaner started....")
    while True:
        try:
            seven_days_ago = timezone.now() - timedelta(days=7)
            models.BotLogs.objects.filter(created__lt=seven_days_ago).delete()
            models.BotOrders.objects.filter(created__lt=seven_days_ago).delete()
            models.BotSignals.objects.filter(created__lt=seven_days_ago).delete()
            print("database_Clenear() --- older data deleted.")
        except:
            print("Error in Removing old records")
        time.sleep(86400)