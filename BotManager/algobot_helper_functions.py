import datetime
import threading
import math
from time import sleep
import pandas_ta as ta
import pandas as pd
from binance.error import ClientError
pd.set_option('display.max_columns', None)

from . import models

volume = 4  # volume for one order (if its 10 and leverage is 10, then you put 1 usdt to one position)
leverage = 3      # total usdt is 5*2=10 usdt
order_type = 'ISOLATED'  # type is 'ISOLATED' or 'CROSS'


def get_balance_usdt(client):
    print("----fetching Balance")
    models.BotLogs(description=f'----fetching Balance').save()
    try:
        response = client.balance(recvWindow=10000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])

    except ClientError as error:
        print(
            "----fetching Balance Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----fetching Balance Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

def all_usdt_pairs(client):
    # Fetch exchange info to get all symbols
    exchange_info = client.exchange_info()

    # Filter USDT futures pairs
    usdt_futures_pairs = [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['quoteAsset'] == 'USDT']
    return  usdt_futures_pairs

def fetch_historical_data(client_obj, symbol, interval='5m',limit=1000):
    print("----fetching Historical data")
    models.BotLogs(description=f'----fetching Historical Data').save()
    try:
        resp = pd.DataFrame(client_obj.klines(symbol, interval,limit=limit))
        resp = resp.iloc[:, :6]
        resp.columns = ['Time', 'open', 'high', 'low', 'close', 'volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as error:
        print(
            "----fetching Historical data Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----fetching Historical data Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()


# Set leverage for the needed symbol. You need this bcz different symbols can have different leverage
def set_leverage(client,symbol, level):
    print("----setting Leverage")
    models.BotLogs(description=f'----Setting Leverage').save()
    try:
        response = client.change_leverage(
            symbol=symbol, leverage=level, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "----setting Leverage Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----setting Leverage Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

# The same for the margin type
def set_mode(client, symbol, order_type):
    print("----Setting Mode ")
    models.BotLogs(description=f'----Setting Mode').save()
    #print("inside set mode function")
    try:
        response = client.change_margin_type(
            symbol=symbol, marginType=order_type, recvWindow=6000
        )
        print(response)
    except ClientError as error:
        print(
            "----Setting Mode Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Setting Mode Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

# Price precision. BTC has 1, XRP has 4
def get_price_precision(client, symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['pricePrecision']

# Amount precision. BTC has 3, XRP has 1
def get_qty_precision(client, symbol):
    resp = client.exchange_info()['symbols']
    for elem in resp:
        if elem['symbol'] == symbol:
            return elem['quantityPrecision']

def remove_pending_orders_repeated(client):
    print("----Removing Pending Orders ")
    models.BotLogs(description="----Removing Pending Orders").save()
    while True:
        try:
            minutes = datetime.datetime.now().minute
            if minutes % 15 == 0:
                sleep(60)
            pos = get_pos(client)
            #print(f'You have {len(pos)} opened positions:\n{pos}')
            #if len(pos) == 0:
            #sleep(10)
            ord = check_orders(client)
            # print(ord)
            # removing stop orders for closed positions
            for elem in ord:
                #print("---for removing orders ",elem)
                if (not elem['symbol'] in pos):  #and (elem['type'] not in ['MARKET','LIMIT']):
                    print(elem, "order removed by pending order close function")
                    sleep(1)
                    close_open_orders(client, elem['symbol'])
            sleep(60)
        except ClientError as error:
            print(
                "----Removing Pending Orders  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(description="----Removing Pending Orders  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()
            sleep(60)
            continue
        except:
            models.BotLogs(description="----Error in Removing Pending Orders ").save()
            sleep(60)
            continue


def trailing_sl(client, order_details, qty,sl_data):
    print("----Modify Stoploss")
    #{"Trailing_SL1":Trailing_SL1,"Trailing_SL_Condition1":Trailing_SL_Condition1}
    #sleep(60*5)
    price_condition = False
    while True:
        sleep(5)
        current_price = float(client.ticker_price(order_details['symbol'])['price'])
        #print("stop loss current price",current_price)
        # stop loss order is reverse of limit order. ex. if buy stoploss order will be sell, if sell stoploss will be buy
        if order_details['side'] == 'SELL' and current_price>=sl_data['Trailing_SL_Condition1']:
            price_condition=True
        elif order_details['side'] == 'BUY' and current_price<=sl_data['Trailing_SL_Condition1']:
            price_condition = True
        if price_condition:
            try:
                response = client.get_open_orders(
                    symbol=order_details['symbol'], orderId=int(order_details['orderId']),recvWindow=5000
                )
                if response['status']=='FILLED' or response['status']=='PARTIALLY_FILLED' or response['status']=='CANCELED':
                    break
                if response['status']=='NEW':
                    client.cancel_order(
                        symbol=order_details['symbol'], orderId=int(order_details['orderId']), recvWindow=5000)
                    # Create a new stop-loss order with the updated price
                    try:
                        resp2 = client.new_order(
                            symbol=order_details['symbol'], side=order_details['side'],
                            type='STOP', quantity=qty, timeInForce='GTC',
                            stopPrice=sl_data['Trailing_SL1'],
                            price=sl_data['Trailing_SL1'])

                        # Assuming the new order was created successfully, return its details
                        # return resp2
                        print("----sl modified")
                        print(resp2)
                    except Exception as e:
                        print("----Modify Stoploss Error modifying stop-loss order:", e)
                        # return None
            except Exception as e:
                print("----Modify Stoploss Error canceling order:", e)

            break
    return None

# Open new order with the last price, and set TP and SL:
def place_order(client,signal,amount):
    # signal =['coinpair', {"side":'sell',"BUY_PRICE":BUY_PRICE, "SL":SL,"TP":TP}]
    print("----Placing Orders ")
    models.BotLogs(description=f'----Placing Orders').save()
    print(signal[0])
    models.BotLogs(description=f'{str(signal[0])}').save()
    symbol=signal[0]
    price = float(client.ticker_price(symbol)['price'])
    #print("current price ",price)
    qty_precision = get_qty_precision(client, symbol)
    #print("qty_precision ", qty_precision)
    #price_precision = get_price_precision(client, symbol)
    #print("price precision",price_precision)
    qty = round(amount/price, qty_precision)
    #print("qty", qty)
    if signal[1]['side'] == 'buy':
        try:
            Limit_price = signal[1]['BUY_PRICE']
            Limit_price_Trigger = signal[1]['BUY_PRICE_Trigger']
            resp1 = client.new_order(symbol=symbol, side='BUY', type='MARKET', quantity=qty,)
            #                         price= Limit_price, stopPrice= Limit_price_Trigger, timeInForce='GTC')
            print(symbol, signal[1]['side'], "placing order")
            models.BotLogs(description=f'{str(symbol)}, {str(signal)} , buy, placing order').save()
            print(resp1)
            models.BotOrders(order_id=str(resp1['orderId']), order_details=str(resp1)).save()
            models.BotLogs(description=f'{str(resp1)}').save()
            sleep(2)
            sl_price = signal[1]['SL']
            sl_price_trigger = signal[1]['SL_Trigger']
            resp2 = client.new_order(symbol=symbol, side='SELL', type='STOP_MARKET', quantity=qty, timeInForce='GTC',
                                     stopPrice=sl_price, closePosition=True) #stopPrice=sl_price_trigger, price=sl_price) #closePosition=True)
            print(resp2)
            models.BotOrders(order_id=str(resp2['orderId']), order_details=str(resp2)).save()
            models.BotLogs(description=f'{str(resp2)}').save()
            #threading.Thread(target=trailing_sl, args=(client, resp2, qty,signal[1]["Trailing_stopLosses"])).start()
            sleep(2)
            tp_price = signal[1]['TP']
            tp_price_trigger = signal[1]['TP_Trigger']
            resp3 = client.new_order(symbol=symbol, side='SELL', type='TAKE_PROFIT', quantity=qty, timeInForce='GTC',
                                     stopPrice=tp_price_trigger, price=tp_price) #closePosition=True)
            print(resp3)
            models.BotOrders(order_id=str(resp3['orderId']), order_details=str(resp3)).save()
            models.BotLogs(description=f'{str(resp3)}').save()
        except ClientError as error:
            print(
                "----Placing Orders buy side  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(description="----Placing Orders buy side  Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()
    if signal[1]['side'] == 'sell':
        try:
            Limit_price = signal[1]['BUY_PRICE']
            Limit_price_Trigger = signal[1]['BUY_PRICE_Trigger']
            resp1 = client.new_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty,)
            #                         price= Limit_price, stopPrice= Limit_price_Trigger, timeInForce='GTC')
            print(symbol, signal[1]['side'], "placing order")
            models.BotLogs(description=f'{str(symbol)}, {str(signal)} , sell side placing order').save()
            print(resp1)
            models.BotOrders(order_id=str(resp1['orderId']), order_details=str(resp1)).save()
            models.BotLogs(description=f'{str(resp1)}').save()
            sleep(2)
            sl_price = signal[1]['SL']
            sl_price_trigger = signal[1]['SL_Trigger']
            resp2 = client.new_order(symbol=symbol, side='BUY', type='STOP_MARKET', quantity=qty, timeInForce='GTC',
                                     stopPrice=sl_price, closePosition=True) #stopPrice=sl_price_trigger, price=sl_price)#closePosition=True)
            # #, workingType="CONTRACT_PRICE" or MARK_PRICE
            print(resp2)
            models.BotOrders(order_id=str(resp2['orderId']), order_details=str(resp2)).save()
            models.BotLogs(description=f'{str(resp2)}').save()
            #threading.Thread(target=trailing_sl, args=(client, resp2, qty,signal[1]["Trailing_stopLosses"])).start()
            sleep(2)
            tp_price = signal[1]['TP']
            tp_price_trigger = signal[1]['TP_Trigger']
            resp3 = client.new_order(symbol=symbol, side='BUY', type='TAKE_PROFIT', quantity=qty, timeInForce='GTC',
                                     stopPrice=tp_price_trigger,price=tp_price) #closePosition=True)
            print(resp3)
            models.BotOrders(order_id=str(resp3['orderId']), order_details=str(resp3)).save()
            models.BotLogs(description=f'{str(resp3)}').save()
        except ClientError as error:
            print(
                "----Placing Orders sell side Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(description="----Placing Orders sell side Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()

# Your current positions (returns the symbols list):
def get_pos(client):
    #print("----Getting Positions ")
    #models.BotLogs(description="----Getting Positions ").save()
    try:
        resp = client.get_position_risk()
        pos = []
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                pos.append(elem['symbol'])
        return pos
    except ClientError as error:
        print(
            "----Getting Positions Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Getting Positions Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

def get_pos_count(client):
    print("----Getting Position Count ")
    models.BotLogs(description="----Getting Position Count ").save()
    try:
        resp = client.get_position_risk()
        position = 0
        for elem in resp:
            if float(elem['positionAmt']) != 0:
                position = position + 1
        return position
    except ClientError as error:
        print(
            "----Getting Position Count Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Getting Position Count Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()


def check_orders(client):
    #print("----Checking Orders ")
    #models.BotLogs(description="----Checking Orders ").save()
    try:
        response = client.get_orders(recvWindow=10000)
        sym = []
        for elem in response:
            sym.append(elem)
        #print("working")
        return sym
    except ClientError as error:
        print(
            "----Checking Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Checking Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()

# Close open orders for the needed symbol. If one stop order is executed and another one is still there
def close_open_orders(client,symbol):
    print("----Closing Open Orders")
    models.BotLogs(description="----Closing Open Orders").save()
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=10000)
        return response
    except ClientError as error:
        print(
            "----Closing Open Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )
        )
        models.BotLogs(description="----Closing Open Orders Found error. status: {}, error code: {}, error message: {}".format(
                error.status_code, error.error_code, error.error_message
            )).save()


def calculate_incr(df):
    ema_data=df['ema5'].tolist()
    incr_data = []
    incr_data.append(0)
    for i in range(1,len(ema_data)):
        if math.isnan(ema_data[i-1]):
            incr_data.append(0)
            continue
        increase = (( ema_data[i] - ema_data[i-1])/ema_data[i-1]) * 100
        incr_data.append(increase)

    return incr_data


def get_signal(df):
    #print("inside get signal")
    #print(df)
    df['ema5'] = ta.ema(df['close'], 5)
    df['incr'] = calculate_incr(df)
    df['superd'] = ta.supertrend(df['high'],df['low'],df['close'],10,1.5)['SUPERTd_10_1.5']
    df['superv'] = ta.supertrend(df['high'], df['low'], df['close'], 10, 1.5)['SUPERT_10_1.5']
    df['bigsuperd'] = ta.supertrend(df['high'], df['low'], df['close'], 10, 3.0)['SUPERTd_10_3.0']
    # Parameters  for big bars ---------------------
    length = 10
    threshold = 0.1
    max_size_multiplier = 3.0
    # Calculate the size of each candle
    df['candle_size'] = abs(df['close'] - df['open'])
    # Calculate the average size of the last `length` candles
    df['average_size'] = df['candle_size'].rolling(window=length).mean()
    # Determine the maximum allowed size based on the average size
    df['max_allowed_size'] = df['average_size'] * max_size_multiplier
    # Determine if the current candle is significantly bigger than the average
    df['is_big_bar'] = (df['candle_size'] > df['average_size'] * threshold) & (
            df['candle_size'] <= df['max_allowed_size'])
    # ------------------------------------------------------
    issell = df['superd'].iloc[-2] == 1 and df['bigsuperd'].iloc[-2] == -1 and \
                  df['superv'].iloc[-2] != df['superv'].iloc[-3] and \
                  df['is_big_bar'].iloc[-2] == True

    isbuy = df['superd'].iloc[-2] == -1 and df['bigsuperd'].iloc[-2] == 1 and \
                  df['superv'].iloc[-2] != df['superv'].iloc[-3] and \
                  df['is_big_bar'].iloc[-2] == True



    df = df.iloc[-2, :]
    print(df)

    price_precision = len(str(df['open']).split('.')[1])
    if len(str(df['high']).split('.')[1]) > price_precision:
        price_precision = len(str(df['high']).split('.')[1])
    if len(str(df['low']).split('.')[1]) > price_precision:
        price_precision = len(str(df['low']).split('.')[1])
    if len(str(df['close']).split('.')[1]) > price_precision:
        price_precision = len(str(df['close']).split('.')[1])

    decimalpoint = float('0.'+'0'*(price_precision-1) + '1')
    triggerdecimalpoint = float('0.' + '0' * (price_precision - 1) + '3')

    if isbuy:
        SLTPRatio = 2  # 1:1.2
        # signal = 1
        BUY_PRICE = round(df['low']-decimalpoint, price_precision)
        BUY_PRICE_Trigger = round(df['low'], price_precision)
        TP = round(df['high']+decimalpoint, price_precision)
        TP_Trigger = TP #round(SL-((SL-BUY_PRICE)/2),price_precision)
        SL = round(BUY_PRICE - SLTPRatio * (TP - BUY_PRICE),price_precision)
        SL_Trigger = round(SL+triggerdecimalpoint,price_precision) #round(TP+((BUY_PRICE-TP)/2),price_precision)
        last_buy_price = round(BUY_PRICE - ((TP - BUY_PRICE) * 0.4), price_precision)
        Trailing_SL1 = round(BUY_PRICE+((TP - BUY_PRICE)*0.2), price_precision)
        Trailing_SL_Condition1 = round(BUY_PRICE + ((TP - BUY_PRICE) * 0.8), price_precision)
        #tp again for double tp
        TP = round((TP + (TP-BUY_PRICE)) + decimalpoint, price_precision)
        TP_Trigger = TP  # round(SL-((SL-BUY_PRICE)/2),price_precision)
        trade = {"side": 'buy',
                 "BUY_PRICE": BUY_PRICE, "BUY_PRICE_Trigger":BUY_PRICE_Trigger,
                 "last_buy_price": last_buy_price,
                 "SL": SL, "SL_Trigger":SL_Trigger,
                 "TP": TP, "TP_Trigger":TP_Trigger,
                 "Trailing_stopLosses":{"Trailing_SL1":Trailing_SL1,"Trailing_SL_Condition1":Trailing_SL_Condition1},
                 }
        # print(trade)
        return trade

    # for long trade
    elif issell:
        SLTPRatio = 2  # 1:1.2
        # signal = 1
        BUY_PRICE = round(df['high']+decimalpoint, price_precision) #df['high']
        BUY_PRICE_Trigger = round(df['high'], price_precision)
        TP = round(df['low'] - decimalpoint, price_precision)  #df['low']
        TP_Trigger = TP  #round(SL + ((BUY_PRICE - SL) / 2), price_precision)
        SL = round(BUY_PRICE + SLTPRatio * (BUY_PRICE - TP),price_precision)
        SL_Trigger = round(SL - triggerdecimalpoint, price_precision)
        last_buy_price = round(BUY_PRICE + ((BUY_PRICE - TP) * 0.4), price_precision)
        Trailing_SL1 = round(BUY_PRICE - ((BUY_PRICE - TP) * 0.2), price_precision)
        Trailing_SL_Condition1 = round(BUY_PRICE - ((BUY_PRICE - TP) * 0.8), price_precision)
        #tp again for double tp
        TP = round((TP - (BUY_PRICE- TP)) - decimalpoint, price_precision)  # df['low']
        TP_Trigger = TP
        trade = {"side": 'sell',
                 "BUY_PRICE": BUY_PRICE, "BUY_PRICE_Trigger":BUY_PRICE_Trigger,
                 "last_buy_price": last_buy_price,
                 "SL": SL, "SL_Trigger":SL_Trigger,
                 "TP": TP, "TP_Trigger":TP_Trigger,
                 "Trailing_stopLosses":{"Trailing_SL1":Trailing_SL1,"Trailing_SL_Condition1":Trailing_SL_Condition1},
                 }
        # print(trade)
        return trade

    return None


def monitor_signal(client,signal_list,coinpair_list):
    print("----Monitor Signal")
    #isOrderPlaced=False
    models.BotLogs(description="----Monitor Signal").save()
    if len(signal_list)==0:
        print("no signal")
        models.BotLogs(description="no signal").save()
        return None
    pos = get_pos(client)
    # if len(pos) != 0:
    #     return None
    ord = check_orders(client)
    # print("old orders ",ord)
    # removing stop orders for closed positions
    for elem in ord:
        if not elem['symbol'] in pos:
            close_open_orders(client, elem['symbol'])
    #loss_count = recent_loss_count(client,coinpair_list)
    #print("recent losses",loss_count)
    leverage = 3
    volume = 4
    ordersList=[]
    for signal in signal_list:
        ordersList.append(signal[0])
        set_mode(client, signal[0], order_type)
        # print("isolated mode set")
        if models.StaticData.objects.exists():
            obj = models.StaticData.objects.get(static_id=1)
            leverage = int(obj.leverage)
            # print("leverage value ",type(leverage),leverage)
        set_leverage(client, signal[0], leverage)  # +(loss_count*2)
        # print("leverage set")
        if models.StaticData.objects.exists():
            obj = models.StaticData.objects.get(static_id=1)
            volume = int(obj.volume)
    print("orders list -- ",ordersList)
    while True:
        try:
            minutes = datetime.datetime.now().minute
            seconds = datetime.datetime.now().second
            if minutes % 15 == 14 and seconds>=30 :
                break
            if len(ordersList)==0:
                break
            for signal in signal_list:
                #print(signal)
                current_price = float(client.ticker_price(signal[0])['price'])
                #print("current price from ticker",current_price,type(current_price))
                #condition for buy or sell then break
                if signal[1]['side']=='sell' and signal[0] in ordersList:
                    if current_price>signal[1]['BUY_PRICE'] and current_price<signal[1]['last_buy_price']:
                        amount = volume * leverage  # (+loss_count)
                        place_order(client,signal,amount)
                        print("order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],amount,leverage))
                        models.BotLogs(description="order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],amount,leverage)).save()
                        ordersList.remove(signal[0])
                        #isOrderPlaced=True
                        #break

                elif signal[1]['side'] == 'buy' and signal[0] in ordersList:
                    if current_price < signal[1]['BUY_PRICE'] and current_price > signal[1]['last_buy_price']:
                        amount = volume * leverage #(+ loss_count)
                        # print('Placing order for ', signal[0])
                        place_order(client, signal, amount)
                        print("order placed for {0} and total money invested {1}, leverage {2} ".format(signal[0],
                                amount, leverage))
                        models.BotLogs(
                            description="order placed for {0} and total money invested {1}, leverage {2} ".format(
                                signal[0], amount, leverage)).save()
                        ordersList.remove(signal[0])
                        #isOrderPlaced = True
                        #break

                sleep(1)
        except ClientError as error:
            print(
                "----Monitor Signal Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )
            )
            models.BotLogs(
                description="----Monitor Signal Found error. status: {}, error code: {}, error message: {}".format(
                    error.status_code, error.error_code, error.error_message
                )).save()
            sleep(5)
            continue
        except :
            print("error in monitor signal")
            models.BotLogs(description="error in monitor signal").save()
            sleep(5)
            continue
    return None