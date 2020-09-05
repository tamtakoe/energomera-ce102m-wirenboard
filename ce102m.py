#!/usr/bin/python
# coding: utf-8
import argparse, io, serial, re, subprocess, threading

# Если нет ключей, то режим чтения по умолчанию
# -r : чтение ограниченного набора параметров
# -f : чтение полного набора параметров
# -p : режим программирования (отменяет -r)
# -s : "silent mode", только для -p, выводятся только данные
# -d : адрес серийного порта (по умолчанию /dev/ttyRS485-2)
# -t : частота опроса датчика, с (по умолчанию 5 с)

parser = argparse.ArgumentParser(description='Energomera CE102M Wirenboard daemon')
parser.add_argument('-r', action="store_true", dest="read", help="Reading a limited set of parameters")
parser.add_argument('-f', action="store_true", dest="full", help="Reading a full set of parameters")
parser.add_argument('-p', action="store_true", dest="programming", help="Programming mode (overrides -r)")
parser.add_argument('-s', action="store_true", dest="silent", help="'silent mode', for -p only, only data is displayed")
parser.add_argument('-a', action="store", dest="address", default='/dev/ttyRS485-2', help="Serial port address (/dev/ttyRS485-2 by default)")
parser.add_argument('-t', action="store", dest="timeout", default=5, type=int, help="Power meter polling rate, s (5 by default)")
args = parser.parse_args()

silent = False
read_flag = '0'
polling_rate = args.timeout
is_daemon_mode = not (args.full or args.read or args.programming)

if args.full:
   print 'Read a full set of parameters of Energomera CE102M'
if args.read:
   print 'Read a limited set of parameters of Energomera CE102M'
   read_flag = '6'
if args.programming:
   print 'Energomera CE102M programming'
   read_flag = '1'
   silent = args.silent
if is_daemon_mode:
   print 'Start Energomera CE102M Wirenboard daemon (updates every ' + str(polling_rate) + 's)'

scope = {
   'silent': silent,
   'upd_counter': 0,
   'data': [
      # f - поле есть в полном, s - в ограниченном наборе данных
      ['STAT_', 'text', ''],              # 03000002                   -f
      ['RECPW', 'text', ''],              # 080BF3CA                   -f
      ['DATE_', 'text', ''],              # 02.01.09.20                -fs
      ['TIME_', 'text', ''],              # 01:38:52                   -fs
      ['WATCH', 'text', ''],              # 01:38:52,02.01.09.20,0     -f
      ['DELTA', 'value', ''],             # 1                          -f
      ['TTOFF', 'value', ''],             # 5                          -f
      ['TRANS', 'value', ''],             # 0                          -f
      ['HOURS', 'value', ''],             # 770                        -f
      ['VINFO', 'text', ''],              # v01.0401;Mar 21 2016       -f
      ['SCSD_', 'text', ''],              # 1,2,1034,1,1,1             -f
      ['ASMBL', 'text', ''],              # D2F8S3P0N0                 -f
      ['MODEL', 'text', ''],              # 0                          -f
      ['SNUMB', 'text', ''],              # 010748140616670            -fs
      ['VOLTA', 'voltage', ''],           # 209.52                 V   -f
      ['CURRE', 'value', ''],             # 0.108                  A   -f
      ['POWEP', 'power_consumption', ''], # 0.020786               kWh -fs
      ['COS_f', 'value', ''],             # 0.906                      -f
      ['FREQU', 'value', ''],             # 49.97                  Hz  -f
      ['HVOLT', 'voltage', ''],           # 253                    V   -f
      ['LVOLT', 'voltage', ''],           # 198                    V   -f
      ['V_RAT', 'value', ''],             # 16648                      -f
      ['I_RAT', 'value', ''],             # 19197                      -f
      ['GCOR1', 'value', ''],             # 16719                      -f
      ['POFF1', 'value', ''],             # 9200                       -f
      ['PCOR1', 'value', ''],             # 0                          -f
      ['MPCHS', 'text', ''],              # C2CB                       -f
      ['ET0PE', 'value', ''],             # 0.93                   kW  -s
      ['IDPAS', 'text', ''],              # 140616670                  -s
      ['GRF01', 'text', ''],              # 07:00:01                   -s
      #['GRF02 .. GRF36']

      # Типы для поля STAT_
      ['Tariff', 'value', ''],                     # 2
      ['Battery discharged', 'alarm', ''],         # 0
      ['Forward direction', 'switch', ''],         # 1
      ['Backward direction', 'switch', ''],        # 0
      ['Capacitive load', 'switch', ''],           # 1
      ['Inductive load', 'switch', ''],            # 0
      ['Time correction exhausted', 'alarm', ''],  # 0
      ['Voltage is normal', 'switch', ''],         # 0
      ['Voltage is upper', 'alarm', ''],           # 0
      ['Voltage is lower', 'alarm', ''],           # 0
      ['Clock error', 'alarm', ''],                # 0
      ['Summer time', 'switch', ''],               # 0
      ['CRC error', 'alarm', ''],                  # 0
      ['Cover was opened', 'alarm', ''],           # 0
      ['Battery expired', 'alarm', ''],            # 0
      ['CRC memory error', 'alarm', ''],           # 0
      ['CRC metrological error', 'alarm', ''],     # 0
      ['Scheduled tariff 1', 'switch', ''],        # 1
      ['Scheduled tariff 2', 'switch', ''],        # 1
      ['Scheduled tariff 3', 'switch', ''],        # 0
      ['Scheduled tariff 4', 'switch', ''],        # 0
      ['Scheduler error', 'alarm', '']             # 0
   ]
}

# Параметры последовательного порта: 9600 бод, 7E1, таймаут > 0.2 с
ser = serial.Serial(args.address, bytesize=serial.SEVENBITS, parity=serial.PARITY_EVEN, timeout = 0.3)
sio = io.TextIOWrapper(io.BufferedRWPair(ser, ser), newline = '')

# Выполнение функции с заданным интервалом
def set_interval(func, arg, sec):
    def func_wrapper():
        func(arg)
        set_interval(func, arg, sec)
    t = threading.Timer(sec, func_wrapper)
    t.start()
    return t

# Узнаем значение бита по его позиции
def bit_at(n, position, invert = False):
    return (n & (1 << position)) >> position ^ int(invert)

# Чтение посылки с проверкой LRC
def data_decode(sdata):
   msg = dict()
   msg['head'] = ''
   msg['body'] = ''
   msg['lrc'] = False

   # Ничего не меняем, если пришли служебные символы (ACK, NAK)
   if len(sdata) <= 1:
      msg['body'] = sdata
      msg['lrc'] = True

   else:
      lrc = 0x00
      head_add = False
      body_add = False
      lrc_add = False

      # Считаем LRC (Сложение всех байт после (SOH) или (STX), не включая,
      # до (ETX) включительно по модулю 0x7f, одновременно читаем заголовок и данные
      for i in range(0,len(sdata)-1):

         # Обнаружен (SOH)
         if sdata[i] == '\x01':
            head_add = True
            lrc_add = True

         # Обнаружен (STX)
         elif sdata[i] == '\x02':
            head_add = False
            body_add = True
            if lrc_add:
               lrc = (lrc + ord(sdata[i])) & 0x7f
            else:
               lrc_add = True

         # Обнаружен (ETX)
         elif sdata[i] == '\x03':
            head_add = False
            body_add = False
            lrc_add = False
            lrc = (lrc + ord(sdata[i])) & 0x7f

         else:
            if head_add:
               msg['head'] += sdata[i]
            elif body_add:
               msg['body'] += sdata[i]
            if lrc_add:
               lrc = (lrc + ord(sdata[i])) & 0x7f

      # Проверяем последний байт посылки на соответствие вычисленому LRC
      msg['lrc'] = lrc == ord(sdata[len(sdata) - 1])

   return msg

# Запись посылки в строку с добавлением вычисленного LRC
def data_encode(msg):
   sdata = ''
   if msg['head']:
      sdata += '\x01' + msg['head']
   if msg['body']:
      sdata += '\x02' + msg['body']
   sdata += '\x03'

   # Вычисление LRC см. data_decode
   lrc = 0x00
   lrc_add = False
   for i in range(0,len(sdata)):
      if sdata[i] == '\x01':
         lrc_add = True
      elif sdata[i] == '\x02':
         if lrc_add:
            lrc = (lrc + ord(sdata[i])) & 0x7f
         else:
            lrc_add = True
      elif sdata[i] == '\x03':
         lrc_add = False
         lrc = (lrc + ord(sdata[i])) & 0x7f
      else:
         if lrc_add:
            lrc = (lrc + ord(sdata[i])) & 0x7f

   # Добавление вычисленного LRC в строку посылки
   sdata += chr(lrc)
   return sdata

# Отправка данных в Wirenboard
def anspub(subtop, val):
   if is_daemon_mode:
      topic = "mosquitto_pub -t '/devices/energomera-ce102m/controls/" + subtop + "' -m '" + str(val) + "'"
      subprocess.call(topic, shell='True')
   else:
      print(subtop, val)
   return 1

# Установка типов данных в Wirenboard
def set_types():
   topic = "mosquitto_pub -t '/devices/energomera-ce102m/meta/name' -m 'Energomera CE102M'"
   subprocess.call(topic, shell='True')

   for item in scope['data']:
      topic = "mosquitto_pub -t '/devices/energomera-ce102m/controls/" + item[0] + "/meta/type' -m '" + item[1] + "'"
      subprocess.call(topic, shell='True')

      topic = "mosquitto_pub -t '/devices/energomera-ce102m/controls/" + item[0] + "/meta/readonly' -m '1'"
      subprocess.call(topic, shell='True')
   return 1

# Обновление поля данных
def update_data(key, value):
   for item in scope['data']:
      if (item[0] == key):
         item[2] = value
         return 1

# Отправка имеющихся данных в Wirenboard
def send_data():
   for item in scope['data']:
      anspub(item[0], item[2])

# Вывод ошибки
def set_error(error = 'Device error'):
   topic = "mosquitto_pub -t '/devices/energomera-ce102m/meta/error' -m '" + error + "'"
   subprocess.call(topic, shell='True')

# Отправка посылки и чтение данных из последовательного порта
def send_read(sdata):
   sio.write(unicode(sdata))
   sio.flush()
   return sio.read().encode('ascii')

# Подключение и получение данных счетчика
def get_info(scope):
   # Пароль для режима программирования (заводской: 777777)
   # Если не указан, будет запрошен
   password = ''

   # Завершаем предыдущий сеанс
   send_read(data_encode({'head':'B0','body':''}))

   # Получаем идентификационное сообщение в ответ на общий запрос
   ident = send_read('/?!\r\n')

   # Каждый пятый раз получаются все данные, остальные разы - ограниченный набор
   is_short_session = is_daemon_mode and scope['upd_counter'] % 5 != 0

   scope['upd_counter'] += 1
   print '\n#' + str(scope['upd_counter']) + ' Connect to ' + str(ident).replace('\n', '')

   silent = scope['silent']

   # Отправляем подтвеждение с выбором режима и получаем информационное сообщение
   message = data_decode(send_read('\x060' + ident[4] + ('6' if is_short_session else read_flag) + '\r\n'))

   # Продолжаем, пока не получено сообщение окончания сеанса (B0)
   while message['head'] <> 'B0':

      # Запрошен пароль для режима программирования
      if message['head'] == 'P0':
         if password == '':
            try:
               password = raw_input('' if silent else 'Enter password '+ message['body'] + ': ')
            except (EOFError):
               send_read(data_encode({'head':'B0', 'body':''}))
               break
         message = data_decode(send_read(data_encode({'head':'P1', 'body': '(' + password + ')'})))

      # Получен запрос повторения (NAK)
      # Почему-то после этого счетчик не ждет повторения, а просто перестает отвечать
      # Начинаем сначала
      elif message['body'] == '\x15':
         if not silent:
            print '(NAK) received, restarting...'
         send_read(data_encode({'head':'B0','body':''}))
         ident = send_read('/?!\r\n')
         message = data_decode(send_read('\x060' + ident[4] + read_flag + '\r\n'))

      # Нет ответа - начинаем сначала
      elif message['body'] == '':
         if not silent:
            print 'Timeout, restarting...'
         send_read(data_encode({'head':'B0','body':''}))
         ident = send_read('/?!\r\n')
         message = data_decode(send_read('\x060' + ident[4] + read_flag + '\r\n'))

      else:

         # Получено сообщение подтверждения
         if message['body'] == '\x06':
            if not silent:
               print '(ACK)'

         else:

            # Получено информационное сообщение
            if message['lrc']:
               # Устанавливаем типы данных счетчика в WB (можно делать один раз, но для надежности определяем типы перед каждой отправкой)
               if not is_short_session:
                  print 'Set WB data types'
                  set_types()

               # Парсим и отправляем данные в WB
               print 'Transfer data to WB' + (' (limited set of parameters)' if is_short_session else '') + '...'
               for line in message['body'].split('\n'):
                  val = re.search('(.+)\((.*)\)', line)
                  if val:
                     parameter = val.group(1)
                     value = val.group(2)
                     update_data(parameter, value)

                     if parameter == 'STAT_':
                        value = int(value, 16)
                        update_data('Tariff', value & 7)
                        update_data('Battery discharged', bit_at(value, 3))
                        update_data('Forward direction', bit_at(value, 7, True))
                        update_data('Backward direction', bit_at(value, 7))
                        update_data('Capacitive load', bit_at(value, 8, True))
                        update_data('Inductive load', bit_at(value, 8))
                        update_data('Time correction exhausted', bit_at(value, 9))
                        update_data('Voltage is normal', int(not(value & 3072)))
                        update_data('Voltage is upper', bit_at(value, 10))
                        update_data('Voltage is lower', bit_at(value, 11))
                        update_data('Clock error', bit_at(value, 12))
                        update_data('Summer time', bit_at(value, 14))
                        update_data('CRC error', bit_at(value, 16))
                        update_data('Cover was opened', bit_at(value, 17))
                        update_data('Battery expired', bit_at(value, 19))
                        update_data('CRC memory error', bit_at(value, 20))
                        update_data('CRC metrological error', bit_at(value, 21))
                        update_data('Scheduled tariff 1', bit_at(value, 24))
                        update_data('Scheduled tariff 2', bit_at(value, 25))
                        update_data('Scheduled tariff 3', bit_at(value, 26))
                        update_data('Scheduled tariff 4', bit_at(value, 27))
                        update_data('Scheduler error', bit_at(value, 28))
               send_data()
               print 'Success'
            else:
               print 'Data is corrupt!'
               set_error('Data is corrupt!')

         # Если режим чтения, выходим
         if not (read_flag == '1'):
            break

         # Ввод типа команды (чтение, запись или выход)
         # Поддерживаются только R1, W1 и B0
         try:
            head = raw_input('' if silent else '(R)ead, (W)rite or e(X)it (default)? ')
         except (EOFError):
            send_read(data_encode({'head':'B0','body':''}))
            break

         # Ввод команды и отправка
         if (head.upper() == 'R') or (head.upper() == 'W'):
            try:
               body = raw_input('' if silent else 'Enter command: ')
            except (EOFError):
               send_read(data_encode({'head':'B0','body':''}))
               break
            message = data_decode(send_read(data_encode({'head':head.upper()+'1','body':body})))

         # Завершение сеанса
         else:
            send_read(data_encode({'head':'B0','body':''}))
            break
   print 'Disconnect'

if is_daemon_mode:
   # Периодически опрашиваем счетчик
   set_interval(get_info, scope, polling_rate)
else:
   # Настраиваем счетчик или выводим данные в консоль
   get_info(scope)