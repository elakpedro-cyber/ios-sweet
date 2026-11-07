# iOS Sweet → Redmi 9T NFC: первый этап, 2026-11-07

Рабочая копия: `ios-lemon`, основа `dipa-studio/ios-sweet`,
upstream commit `45263bee51df4a0f55cdf9c649af886399488ddb`.
Это начало переноса, а не готовая прошивка iOS для Redmi 9T.

## Обновление: образ CPU-теста подготовлен

Телефон остаётся в TWRP, ядро recovery 4.19.252. У него `CONFIG_KEXEC=n`,
нет `/proc/kcore`, `/dev/mem`, `/proc/kallsyms`, включена обязательная подпись
модулей. Эти способы чтения аппаратного MMFR0 из recovery недоступны.

Новый Image сохраняет MMFR0 в переменной, доступной для проверки эмулятором.
`tools/verify-lemon-probe.py` действительно запускает его в QEMU 8.2.2:

- Cortex-A53: MMFR0=0x1122, TGran16=0 — PASS.
- Cortex-A76: MMFR0=0x101122, TGran16=1 — PASS.

Это проверка кода теста, не измерение процессора телефона.
В обоих случаях проверены заголовок ARM64 Image, совпадение упакованного ядра
после gzip-распаковки и побайтовое совпадение DTB с текущим boot.

Упаковка:

```sh
bash shim/package-lemon-probe.sh ../../Redmi9T-Native-Linux/tools/mkbootimg.py
python3 tools/unpack_bootv2.py shim/out/lemon-probe/boot-lemon-cpu-probe.img shim/out/lemon-probe/unpacked
python3 tools/verify-lemon-probe.py
```

`shim/out/lemon-probe/boot-lemon-cpu-probe.img`: 315392 байта,
SHA256 `3e3b20d8fcaae8ce542c9f5eba2683231215eba34a9d85e4e66ca0d5c8d25f73`.
Raw Image SHA256 теперь
`350667d2c65e2c3b7f99c6060b59aeff94286aad6833e0162e4b2849b1f3e917`.
Boot v2 сохраняет адреса, размер страницы, OS version и patch level текущего
boot. DTB взят из уже загружавшегося Linux; ramdisk — пустой gzip cpio.
Проверка репозитория проходит: 81 патч, 16 Python, 9 shell.

С телефона дополнительно прочитаны recovery и dtbo. Полные SHA256 на ПК
совпали с чтением соответствующих разделов в recovery:

| Копия в `backup/` | Байты | SHA256 |
|---|---:|---|
| boot-current.img | 134217728 | f5ee6f406dc2a923dae167b9d45287daa0cba3c051484ce6e03536894b6c868f |
| recovery-current.img | 134217728 | 1737005c5d9452d3238fcd0a2430956e7232937b35e9df427edc114f0dacd2eb |
| dtbo-current.img | 16777216 | 6fd8b752c9a64bc77ccb43a43834b38a2a61e0499c44de01c6d1a349d73ce9a6 |

На момент подготовки заряд 11%, USB показывает Charging. Телефон не
перезагружался, ни один раздел не записывался. Аппаратный тест пока не проведён.

### Подготовленный аппаратный сценарий — ещё не разрешён и не выполнен

После зарядки и отдельного подтверждения записи **только boot**:

1. Сверить образ и резервные копии по SHA256 выше; повторно подтвердить
   recovery/ADB и те же symlink путей boot/recovery.
2. Передать тест в `/tmp` TWRP, проверить его SHA256 на телефоне.
3. Записать его в `/dev/block/by-name/boot`, выполнить sync и проверить SHA256
   первых 315392 байт boot. До reboot проверить неизменность recovery/dtbo.
   При ошибке оставаться в TWRP, не перезагружаться.
4. Перезагрузить system; снять с экрана MMFR0 и TGran16. После завершения тест
   останавливается, USB/ADB у него нет. Если изображения нет, это не доказывает
   неподдерживаемый размер страниц. Удержанием Power и Volume Up вернуться
   в сохранённый TWRP; этот возврат требует физического участия пользователя.
5. Вернуть `backup/boot-current.img` в тот же boot и проверить полный SHA256.
   Оставить телефон в TWRP. Recovery не заменять ни на одном шаге.

Восстановление boot (пример из корня `ios-lemon`, только в согласованном тесте):

```powershell
..\platform-tools\adb.exe push backup/boot-current.img /tmp/lemon-boot-restore.img
..\platform-tools\adb.exe shell 'sha256sum /tmp/lemon-boot-restore.img'
# Выполнять запись только если SHA256 совпадает с таблицей.
..\platform-tools\adb.exe shell 'dd if=/tmp/lemon-boot-restore.img of=/dev/block/by-name/boot bs=4096 && sync'
..\platform-tools\adb.exe shell 'sha256sum /dev/block/by-name/boot /dev/block/by-name/recovery /dev/block/by-name/dtbo'
```

Подтверждение записи boot запрошено согласно AGENTS.md. Общее «делаем»
использовано для подготовки; согласие на изменение раздела ещё не получено.

## Что проверено на подключённом телефоне

ADB работает в recovery. `ro.product.device=lemon`, платформа `bengal`,
SoC ID 444, revision 1.0. Из устройства прочитаны текущий boot и живой FDT;
они лежат в исключённых из git каталогах `backup/` и `dtb/`.
Текущий boot уже содержит экспериментальный Linux (`rdinit=/init` и
`clk_ignore_unused` в заголовке); его нельзя называть заводским Android boot.

| Узел | Sweet | Подключённый lemon, живой FDT |
|---|---|---|
| GICD | 0x17a00000 | 0x0f200000 |
| GICR | 0x17a60000 | 0x0f300000, размер 0x100000, stride 0x20000 |
| UFS host | 0x01d84000 | 0x04804000 |
| DWC3 | другой адрес, см. патчи Sweet | 0x04e00000 |
| Splash reservation | 0x9c000000 | 0x5c000000, размер 0xf00000 |
| Панель | 1080×2400 | профиль 1080×2340, nt36672d_xinli_v2_video |
| Сенсор | Goodix, I²C | NVT, SPI1.1; recovery сообщает NT36672A, FW5 |
| CPU MPIDR в DT | 0,100,…,700 | 0,1,2,3,100,101,102,103 |
| PSCI | SMC | `arm,psci-1.0`, `method=smc` |
| Timer | 19.2 MHz, virtual INTID19 | DT: 19.2 MHz, virtual PPI3 → INTID19 |

RAM в текущем FDT: `0x40000000 + 0x3dd00000` и
`0x80000000 + 0xc0000000`. Reserved-memory содержит защищённые области.
Параметры `--highmem` Sweet (почти 4 GiB начиная с 4 GiB) сюда не подходят.
Выбор непрерывного свободного диапазона XNU ещё не выполнен.

Профиль панели из нынешнего cmdline и dmesg отличается от старых отчётов
`Redmi9T-Native-Linux`, где был `td4330_truly_v2_video`.
Причина расхождения неизвестна; старую идентификацию не принимать за текущую.
Splash reservation не доказывает действующий scanout. Адрес/stride для
диагностики взяты из FDT и прежнего simplefb-профиля; вывод нового shim на LCD
ещё не проверялся.

## Проверка размера страниц

Sweet использует аппаратные страницы 16 KiB. До переноса XNU нужно напрямую
прочитать `ID_AA64MMFR0_EL1.TGran16` на lemon.

Собран и запущен в `/tmp` recovery `tools/lemon-cpu-check.c` (static ARM64,
`-Wall -Wextra -Werror`). Привязка потока к каждому из восьми CPU успешна:
MIDR CPU0–3 `0x51af8014`, CPU4–7 `0x51af8002`.
Во всех случаях EL0 MRS вернул MMFR0 `0xff000000`.
Такой результат объявляет неподдерживаемыми сразу все размеры страниц,
включая используемые Linux, и не является достоверным аппаратным MMFR0.
Linux эмулирует доступ к ID-регистрам и скрывает часть полей.
**Поддержка 16 KiB пока не установлена**, отсутствие тоже не доказано.

Подготовлен отдельный bare-metal `shim/lemon-probe.c`, использующий ARM64
entry и экранную консоль исходного проекта. Он читает MMFR0 непосредственно
на EL1, печатает MIDR, MPIDR, EL, SCTLR, частоту таймера и останавливается.
Доступа к UFS, загрузки XNU, запуска вторичных CPU, изменения MMU/GIC,
прошивки и автоматической перезагрузки в нём нет. Пишет только в предполагаемый
splash framebuffer. Проверяет только CPU, на котором стартовал загрузчик.

Сборка в WSL Ubuntu-24.04:

```sh
bash shim/build-lemon-probe.sh
```

Результат `shim/out/lemon-probe/Image` — сырой ARM64 Image, **не Android
boot.img**. Скомпилирован офлайн; на телефоне не запускался. Entry наследует
предположение Sweet: EL1, MMU и D-cache выключены, x0 указывает на FDT.
Эти условия для нового образа также требуют проверки.

Офлайн-проверки пройдены: ARM64 cross-compile с `-Werror`, отсутствие ABS64
в C-объектах и неразрешённых символов в ELF, проверка репозитория
(81 патч, 15 Python и 8 shell-скриптов), `git diff --check`.
Размер Image 77 824 байта, SHA-256:
`102c35dbf0628383bf364f93c0444716031ceab434e0582d3df22e9c3ee996a3`.
Windows checkout изначально создал CRLF в shell-скриптах; рабочие копии этих
скриптов приведены к LF и локально настроен `core.autocrlf=input`.
Содержимое upstream-скриптов при этом не менялось.

## Следующий этап

1. Проверить способ запуска диагностического Image без потери установленного
   Linux. Анализ ABL в старом проекте не нашёл обработчик `fastboot boot`;
   живой ответ в этом сеансе не проверялся. Команду Sweet нельзя переносить
   вслепую. Новый boot.img пока намеренно не упакован.
2. Получить аппаратный MMFR0. При TGran16=0 нужен отдельный перенос XNU на
   поддерживаемую гранулу и проверка совместимости iOS userland. Это не
   исправляется заменой адресов или одного числа PAGE_SIZE.
3. После CPU gate подготовить карту свободной RAM, ADT lemon и ранний вывод
   XNU. Затем отдельно переносить UFS, USB и SPI touchscreen.

Ничего не прошивалось, разделы не менялись, телефон не перезагружался.
Apple-образы и большие rootfs не скачивались. Чужие разрешения на стирание
userdata из upstream NOTES.md к этому телефону не относятся.

Источники:
- [iOS Sweet](https://github.com/dipa-studio/ios-sweet)
- [Arm: Memory management, translation granule](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/LearnTheArchitecture-MemoryManagement-101811_0100_00_en.pdf?revision=1fdc3375-d81c-4457-b786-04fb98557de0)
- [Linux: границы поддерживаемых TGran16](https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/sysreg.h)
