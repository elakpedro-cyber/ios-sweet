# XNU с аппаратными страницами 4 КБ: проверка и первая конфигурация

7 ноября 2026. Телефон на этом этапе не использовался; boot и TWRP не менялись.

## Вывод

В XNU-8796.141.3 есть штатный ARM64 pmap для аппаратных страниц 4 KiB.
Отсутствие 16 KiB granule на проверенном CPU не закрывает перенос XNU.
Подготовлены экспериментальная конфигурация и упаковщик payload для 4 KiB.
Это **не собранное ядро и не готовый boot для телефона**.

XNU различает аппаратную страницу (`ARM_PGBYTES`) и программную страницу VM
(`PAGE_SIZE`). В `osfmk/arm/pmap/pmap.h` есть `PAGE_RATIO`, включая отношение
4:1. В `osfmk/arm/arm_init.c` ядро для RAM >1 GiB намеренно объявляет VM-страницу
16 KiB, даже если аппаратная страница 4 KiB. В `bsd/kern/mach_loader.c`
64-битным приложениям задаётся выравнивание VM map 16 KiB.
Следовательно, поддержка iOS не требует автоматически переводить все её
приложения на программные страницы 4 KiB. Это вывод по исходникам;
dyld/shared cache/launchd из iOS на новой конфигурации пока не запускались.

## Изменения

`xnu/ports/lemon/0001-4k-config.patch` применяется **после** 81 патча Sweet.
При `LEMON_4K=1` и `MACHINE_CONFIG=SWEET` он:

- выбирает ARMv8-A+crypto вместо ARMv8.2-A;
- оставляет `__ARM_16K_PG__` неопределённым, выбирая штатные 4 KiB ветки;
- не включает неподтверждённый PAN;
- выбирает существующий мобильный предел user VA 0xfc0000000 вместо большого
  macOS-предела. Это согласует диапазон с расположением commpage и проверкой
  `ARM_PGSHIFT==12` в `pmap.c`, а не отключает соответствующий static_assert.

Машина остаётся SWEET, чтобы сохранить её опции и staging libpthread/HFS/AES.
Без `LEMON_4K=1` конфигурация Sweet остаётся прежней. Этот отдельный патч
ещё не подключён к GitHub Actions; для будущей macOS-сборки его нужно добавить
после основной серии и передать `LEMON_4K=1` в окружение make/build.sh.

`tools/mkpayload.py --page-size 4096` теперь использует L2-блок 2 MiB и
выравнивание аппаратных страниц 4 KiB. По умолчанию сохраняются прежние
16 KiB и 32 MiB. Передаваемый размер должен совпадать со сборкой ядра:
payload v1 сам не хранит и не проверяет размер страницы ядра.
`shim/loader.c` пока размещает boot_args по границе 16 KiB: это также кратно
4 KiB и не мешает первому варианту; геометрия MMU этим значением не задаётся.

## Проверки

Исходники Apple закреплены на commit
`1b191cb58250d0705d8a51287127505aa4bc0789` (`xnu-8796.141.3`).
Проверено соответствие версии macOS 13.5 по release.json Apple.
Все 81 патч Sweet применены к локальному дереву для анализа;
для двух патчей HFS взяты core-исходники точного HFS commit
`31d5ec238dfab485e78a9a30b8b92d13e8914f03`.
Это проверка применения патчей, не замена полного staging зависимостей SDK.

Дополнительный патч применился с `git apply --check`.
В WSL выполнено:

```sh
python3 tools/test-lemon-4k.py --xnu research/xnu-8796.141.3
python3 tools/validate-repo.py
```

Проверки прошли: ARM_PGSHIFT 12/14, размеры L2 2/32 MiB, TG0/TG1,
предел user VA, отсутствие 16K define/PAN у варианта lemon,
синтетический Mach-O → payload + RAMDisk ADT для обоих размеров,
побайтовое совпадение default payload с явно выбранными 16 KiB.
Общая проверка: 81 патч, 17 Python, 9 shell; `git diff --check` проходит.

Полная компиляция/линковка XNU не выполнялась: на этом Windows/WSL хосте
нет требуемого macOS/Xcode SDK и собранного дерева из CI. Препроцессорная
проверка GCC не подтверждает компиляцию ядра Apple Clang или загрузку XNU.

## Следующая работа

До попытки загрузки нужно исправить раннюю framebuffer-разметку `start.s`:
там остаются адрес 0x9c000000 и предположение об общей L1 записи RAM/FB.
Для 4 KiB одна L1 запись покрывает 1 GiB; framebuffer lemon 0x5c000000
и планируемая RAM ядра могут попасть в разные L1 записи. Слепая замена
32 MiB на 2 MiB не создаст недостающую таблицу. Нужно корректно отобразить
весь framebuffer, а не только один 2 MiB блок.

Затем: карта безопасной RAM/ADT lemon, GIC/ранняя консоль, отключение
неперенесённых UFS/USB/touch драйверов Sweet, сборка и ранняя загрузка в QEMU.
SMP сначала оставить выключенным (`cpus=1`): MPIDR топология lemon другая.
Новый аппаратный boot сейчас не подготовлен и не предлагается к записи.

Источники:
- [Apple XNU: pmap.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm/pmap/pmap.h)
- [Apple XNU: arm_init.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm/arm_init.c)
- [Apple XNU: proc_reg.h](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/osfmk/arm64/proc_reg.h)
- [Apple XNU: mach_loader.c](https://github.com/apple-oss-distributions/xnu/blob/xnu-8796.141.3/bsd/kern/mach_loader.c)
- [Apple macOS 13.5 release.json](https://github.com/apple-oss-distributions/distribution-macOS/blob/macos-135/release.json)
