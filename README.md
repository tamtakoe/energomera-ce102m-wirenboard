# Energomera CE102M adapter
Wirenboard (MQTT) adapter for Energomera CE102M RS-145A power meter

Скрипт, считывающий данные с электросчетчика Энергомера CE102М по RS-485 и передающий их в MQTT каналы контроллера Wirenboard

Подключаем выводы A, B и GND WirenBoard к контактам 9, 10 и 11 счетчика.

Систему команд смотрим в [инструкции к счетчику](http://www.energomera.ru/documentations/ce102m_full_re.pdf)

Протокол обмена данными: [ГОСТ Р МЭК 61107-2001](http://standartgost.ru/g/%D0%93%D0%9E%D0%A1%D0%A2_%D0%A0_%D0%9C%D0%AD%D0%9A_61107-2001)

#### Настройка автозапуска
Создать или отредактировать `/etc/rc.local`

```shell script
#!/bin/sh -e
python /usr/share/wb-mqtt-serial/user-devices/ce102m.py
exit 0
```
`/usr/share/wb-mqtt-serial/user-devices/ce102m.py` - путь до скрипта

#### Запуск в режиме демона (периодический опрос и отсылка данных в Wirenboard)
```shell script
 python ce102m.py

 # Опрос счетчика и каждые 10 с (По умолчанию 5 с)
 python ce102m.py -t 10
```

#### Запуск в режиме программирования
```shell script
 python ce102m.py -p

 # silent mode - выводятся только данные
 python ce102m.py -p -s
```

#### Вывод информации в консоль
```shell script
 # Вывод полной информации
 python ce102m.py -f

 # Вывод ограниченной информации
 python ce102m.py -r
```

#### Настройки
```shell script
 # Настройка серийного порта (По умолчанию /dev/ttyRS485-2)
 python ce102m.py -a /dev/ttyRS485-1
```

Взято за основу: https://support.wirenboard.com/t/schityvanie-pokazanij-i-programmirovanie-elektroschetchika-energomera-se102m-po-rs-485/212