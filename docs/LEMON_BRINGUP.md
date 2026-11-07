# iOS Sweet → Redmi 9T NFC: первый этап, 2026-11-07

Рабочая копия: `ios-lemon`, основа `dipa-studio/ios-sweet`,
upstream commit `45263bee51df4a0f55cdf9c649af886399488ddb`.
Это начало переноса, а не готовая прошивка iOS для Redmi 9T.

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
