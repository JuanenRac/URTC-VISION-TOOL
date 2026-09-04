<p align="center">
  <img src="/images/URTC_VISION_TOOL_BANNER.svg" alt="URTC Visión Tool Logo" width="100%">
</p>

# 👁️ URTC-VISION-TOOL

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | 🇮🇹 <b>Italiano</b> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 🔬 Testina Integrata che Combina Percezione Termica e RGB

<p align="left">
  <img src="https://img.shields.io/badge/Licencia-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Sensors-Thermal%20%2B%20RGB-orange.svg" alt="Sensors">
  <img src="https://img.shields.io/badge/Platform-URTC%20%2F%20CAN-blue.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Stack-C%20%2F%20Python-3776AB.svg" alt="C/Python">
</p>

---

## 1. 🛠️ PANORAMICA TECNICA

**URTC-VISION-TOOL** è una testina robotica specializzata che fonde percezione visiva e termica in un unico effettore compatibile URTC. Progettata per QA avanzato, ispezione termica di PCB e allineamento Pick-and-Place ad alta precisione.

Dotata di una fotocamera RGB a otturatore globale e di un sensore termico della famiglia MLX9064x, fornisce al Vision AI Node dati a doppia modalità, permettendogli di rilevare non solo la presenza di un componente ma anche la sua temperatura di funzionamento o la dissipazione termica di una saldatura.

Non esiste ancora un PCB/schematico per questa scheda (vedi `hardware/`), quindi nulla di sottostante può pilotare sensori termici/RGB reali - ma la toolchain del firmware e la pipeline di visione lato host (generazione sintetica di frame, rendering a falsi colori, allineamento ROI RGB->termico ed estrazione di statistiche di temperatura, tutto coperto da pytest) sono reali e funzionano oggi.

### Caratteristiche Principali:
* 🔬 **Percezione Dual-Modale** — cattura sincronizzata di immagini Termiche e RGB. *(la pipeline di elaborazione alimentata da entrambi i frame è reale - vedi sotto; la cattura sincronizzata reale richiede il PCB e i sensori.)*
* 🌡️ **Termico ad Alta Precisione** — supporto integrato per sensori MLX90640/41/42. *(il rendering a falsi colori e l'estrazione di statistiche per regione sono reali - vedi sotto; leggere un vero MLX9064x via I2C richiede il PCB.)*
* 🎯 **Allineamento Eye-in-Hand** — PnP e AOI (Ispezione Ottica Automatizzata) sub-millimetrica. *(la mappatura di coordinate ROI RGB->termico e l'estrazione di statistiche di temperatura sono reali e testate - vedi `vision_companion/alignment.py` sotto; la precisione sub-millimetrica richiede una vera fotocamera calibrata.)*
* 📡 **API CAN Unificata** — integrata perfettamente nel catalogo di 25 utensili di URTC. *(il protocollo cablato lato sensore stesso - framing, CRC, validazione dell'intervallo - è reale, vedi sotto; serve ancora un vero transceiver CAN per trasportarlo davvero.)*
* 🔒 **Sicurezza del Protocollo Sensore** — framing versionato reale con checksum CRC8, validazione reale dell'intervallo di misura, limitazione della velocità reale, e contatori di diagnostica dedicati per errori/latenza/reset del bus. *(implementato)*
* ✅ **Toolchain firmware Cortex-M4F** — un'immagine bare-metal reale che compila e collega davvero con `arm-none-eabi-gcc`, la stessa toolchain dei repository gemelli URTC e URTC-SMART-RACK. *(implementato — vedi COMPILAZIONE sotto)*
* ✅ **Pipeline di elaborazione `vision_companion`** — un pacchetto Python reale e funzionante: generazione sintetica di frame termici+RGB, rendering termico a falsi colori, allineamento ROI RGB->termico + estrazione di statistiche di temperatura, report statistico, tutto coperto da 21 casi pytest reali, funziona end-to-end senza hardware collegato. *(implementato — vedi COMPAGNO DI VISIONE sotto)*

---

## 2. 🔄 FLUSSO DELLA TESTINA DI VISIONE

```mermaid
flowchart LR
    TOOL["URTC-VISION-TOOL"] --> RGB["Fotocamera RGB (USB 3.0)"]
    TOOL --> THRM["Sensore Termico (CAN / I2C)"]
    RGB --> VISION["VISION-NODE (Hailo-8)"]
    THRM --> CORE["Nucleo HYDRA-UMC (STM32)"]
    VISION --> SYNC["Fusione Multi-Modale"]
    CORE --> SYNC
    SYNC --> DASH["Dashboard di Studio"]
```

---

## 3. 🧱 ARCHITETTURA E DECISIONI DI PROGETTAZIONE

* **Perché questo progetto ha 2 tracce di versione indipendenti.** `src/firmware_common.h` (il firmware lato STM32) e `src/vision_companion/pyproject.toml` (un pacchetto Python separato lato host) sono versionati indipendentemente - girano su hardware diverso (MCU contro host CM5/PC) e vengono pubblicati con calendari diversi.
* **Perché non è un figlio di URTC stesso.** Stesso motivo del README proprio di URTC-SMART-RACK - uno Strumento Complementare che condivide il bus CAN/le convenzioni firmware di URTC, senza far parte della sua gerarchia di integrazione.
* **Perché un pacchetto companion lato host.** La cattura dual-modale termica/RGB richiede una vera elaborazione immagini (numpy/Pillow) che non ha posto sull'STM32 stesso - il pacchetto companion è dove ciò avviene realmente, parlando con la scheda via CAN.
* **Perché `alignment.py` assume un campo visivo condiviso invece di una vera omografia.** Entrambi i sensori sono sulla stessa testina fisica rigida, quindi un riscalamento lineare per asse tra le coordinate pixel in spazio RGB e spazio termico è un'approssimazione v0 ragionevole - una vera calibrazione per pixel (scacchiera, distorsione della lente) richiede vere fotocamere su cui calibrarsi, che non esistono ancora.
* **Come si inserisce nel resto dell'ecosistema.** Condivide il bus CAN/ecosistema utensili proprio di URTC, e forma un abbinamento naturale con HYDRA-UMC-DETECTION-HEF per lo stesso ruolo di riconoscimento visivo che svolge anche URTC-SMART-RACK.
* **Perché il protocollo di trama del sensore porta il proprio campo di timestamp.** Un vero timestamp in millisecondi lato sensore permette a chi chiama di sapere *quando* una lettura è stata effettivamente presa, indipendentemente da quando l'MCU riesce ad analizzare il frame - un reale valore storico/diagnostico che una semplice assunzione di "appena arrivato" farebbe perdere.
* **Perché i contatori di diagnostica (`sensor_diagnostics.c`) non prendono mai da soli una decisione di accettazione/rifiuto.** Solo `sensor_frame.c` (framing), `sensor_reading.c` (intervallo) e `rate_limiter.c` (limitazione della velocità) decidono se un frame è affidabile - la diagnostica si limita a registrare ciò che hanno deciso. Mantenere questo confine rigido significa che un bug nella diagnostica non può mai lasciar passare accidentalmente dati errati, la stessa "separar diagnostico de salida de control" dell'audit di promozione.

---

## 📂 STRUTTURA DELLE DIRECTORY

```text
URTC-VISION-TOOL/
├── src/
│   ├── firmware_common.h           # FIRMWARE_VERSION_MAJOR/MINOR/PATCH = 0.0.0
│   ├── sensor_frame.h / .c         # Reale: formato di frame versionato + parsing/codifica CRC8
│   ├── sensor_reading.h / .c       # Reale: decodifica lettura termica + validazione intervallo
│   ├── rate_limiter.h / .c         # Reale: limitazione frame a intervallo minimo
│   ├── sensor_diagnostics.h / .c   # Reale: contatori errori/latenza/reset bus, separati dal controllo
│   ├── main.c                      # Punto di ingresso minimo (ciclo di battito di vita)
│   ├── startup_stm32_minimal.c     # Tabella dei vettori + Reset_Handler (ancora senza HAL ST, vedi intestazione del file)
│   ├── STM32_MINIMAL.ld            # Linker script placeholder (base 128K FLASH / 32K RAM)
│   └── vision_companion/           # Pipeline di visione Python lato host (CM5/macchina di sviluppo)
│       ├── pyproject.toml          # Packaging + console script `vision-companion`
│       ├── requirements.txt        # numpy + pillow
│       ├── main.py                 # CLI reale e funzionante (version / selftest / analyze-roi)
│       ├── alignment.py            # Reale: mappatura ROI RGB<->termico + estrazione statistiche di temperatura
│       ├── tests/                  # 21 casi pytest reali (main.py + alignment.py)
│       └── README.md               # Documentazione specifica del companion
├── tests/                          # Harness di test firmware nativo host reale (sensor_frame, sensor_reading, rate_limiter, sensor_diagnostics, scenari sensore)
├── docs/                           # Documentazione e riferimento di calibrazione
├── hardware/                       # File di progettazione hardware (PCB, case) - vuoto, nessuno schematico ancora
├── firmware/                       # Output di build versionato (.bin/.elf/.hex), commesso come il repository gemello URTC
├── build/                          # Oggetti di build intermedi (ignorato da git)
├── images/                         # Media e diagrammi
├── tools/
│   ├── build_test.py               # Controllo build/compilazione senza incremento di versione
│   └── ci_validate.py              # Validazione manifest/CHANGELOG/docs usata dalla CI
├── bump_version.py                 # Incremento versione stile contachilometri (generico, condiviso con URTC / URTC-SMART-RACK)
├── bump_manifest_version.py        # Sincronizza la versione di hydra-umc.project.json con quella nativa (--sync)
├── build_firmware.sh / .bat        # Build reale: test host + incrementa versione + compila + collega + pubblica in firmware/
├── build-test.sh / .bat            # Controllo build/compilazione senza incremento di versione
└── README.md
```

---

## 4. ⚙️ COMPILAZIONE (firmware)

Richiede la toolchain ARM GNU (`arm-none-eabi-gcc`, `arm-none-eabi-objcopy`, `arm-none-eabi-size`) e Python 3.

```bash
# Linux/macOS
chmod +x build_firmware.sh   # una tantum
./build_firmware.sh

# Windows
build_firmware.bat
```

Il build incrementa la versione di `src/firmware_common.h` (regola contachilometri), compila `main.c` e `startup_stm32_minimal.c` per Cortex-M4F, li collega con la mappa di memoria placeholder `STM32_MINIMAL.ld`, e pubblica file `.elf`/`.bin`/`.hex` versionati in `firmware/`. Non c'è ancora nulla da flashare su hardware reale - non esiste un PCB che confermi la parte STM32 target, il pinout, il cablaggio dell'MLX9064x, o l'interfaccia della fotocamera RGB.

## 5. 🐍 COMPAGNO DI VISIONE (Python lato host)

Questa parte funziona oggi, completamente, senza alcun hardware collegato:

```bash
cd src/vision_companion
python3 -m venv .venv
# Linux/macOS:
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py selftest

# Windows:
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py selftest
```

`selftest` genera un frame termico sintetico a forma di MLX9064x (32x24, con un punto caldo tipo punta saldante) e un pattern di test RGB a barre colorate, esegue il rendering/salva entrambi come file reali, e stampa le loro statistiche — prova che la pipeline di elaborazione numpy/Pillow funziona davvero, indipendentemente dal passaggio di cattura reale del sensore che arriverà quando esisterà l'hardware.

`analyze-roi X0 Y0 X1 Y1` mappa un riquadro delimitatore in spazio RGB verso lo spazio termico e riporta statistiche reali di temperatura per quella regione — la logica di allineamento dietro la funzionalità Eye-in-Hand Alignment del README, reale oggi:

```bash
.venv/bin/python main.py analyze-roi 280 210 360 270
```

Output di esempio reale:

```text
RGB ROI (280,210)-(360,270) in a 640x480 frame
  -> thermal stats: min=75.67C max=78.97C mean=77.69C (16 thermal px)
```

21 casi pytest reali coprono sia `main.py` che `alignment.py`:

```bash
pip install -e ".[dev]"
pytest
```

Vedi `src/vision_companion/README.md` per la documentazione completa del companion, e [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) per ogni comando, flag e codice di uscita con output reale catturato.

---

## 6. 📋 CHANGELOG

Consulta [`CHANGELOG.md`](CHANGELOG.md) per la cronologia completa delle versioni — il firmware e `vision_companion` sono versionati in modo indipendente (vedi COMPILAZIONE e COMPAGNO DI VISIONE sopra), e ogni modifica reale ha lì la propria voce.

---

## 🔗 Progetti Correlati

Questo progetto fa parte dell'ecosistema robotico HYDRA-UMC dello stesso autore (JuanenRac / Electro Hobby 3D). Vale la pena conoscerlo, poiché una richiesta potrebbe in realtà riguardare uno di questi invece di questo repository.

**Direttamente Correlati**
- **[URTC](https://github.com/JuanenRac/URTC)** — firmware per la scheda fisica dell'Universal Robot Tool Controller, oltre 25 profili utensile su bus CAN — lo stesso ecosistema di strumenti, sullo stesso bus CAN.
- **[HYDRA-UMC-DETECTION-HEF](https://github.com/JuanenRac/HYDRA-UMC-DETECTION-HEF)** — registro reale di modelli compilati con verifica di caricamento sicuro per architettura Hailo/checksum — un fratello per ruolo nel riconoscimento visivo.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — strumento desktop di diagnostica CAN-bus dal vivo per schede URTC, un pannello per profilo utensile — la propria diagnostica CAN-bus dal vivo completa i controlli visivi di garanzia della qualità di questo strumento sulla stessa testa utensile.

**Fa Anche Parte dell'Ecosistema**

*Hardware e Piattaforma di Base*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — la scheda madre fisica del braccio robotico: host CM5 + coprocessore STM32H745 dual-core, che coordina fino a 8 bracci utensile via CAN-OTA/SPI-OTA.
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — livello prodotto riproducibile su Raspberry Pi OS per il CM5: agente in sola lettura, config/profili validati, provisioning WiFi al primo contatto.
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — il contratto JSON-Schema condiviso e la barriera di sicurezza contro cui ogni bridge valida i propri comandi.

*Backend Centrale e Client*
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — il vero backend headless (REST/WebSocket) con cui parla davvero ogni client di controllo.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — dashboard di controllo web con visualizzazione 3D multi-robot in tempo reale.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — centro di comando sciame desktop (PySide6) per più server contemporaneamente, pacchettizzato come eseguibile standalone.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — app di controllo nativa per Android con login biometrico e un companion Wear OS abbinato.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — app di controllo per iOS/iPadOS (Flutter) con sincronizzazione WebSocket in tempo reale.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — interfaccia touch nativa per il touchscreen DSI da 7" a bordo, incorporata direttamente nel CM5.
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — creatore/editor grafico desktop di URDF che invia i modelli finiti al catalogo di STUDIO.
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — barriera di coordinamento per flotte AGV/AMR tramite un publisher MQTT VDA 5050 reale.
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — coordinatore ad alto livello per celle CNC con accesso reale a stato/byte di controllo GRBL.
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — barriera di coordinamento per droidi con zampe/umanoidi, con un vero mittente di comandi per Boston Dynamics Spot.
- **[HYDRA-UMC-BRIDGE-LASER](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-LASER)** — coordinatore di sicurezza per celle laser che legge 3 salvaguardie GPIO reali di chiave/involucro/interblocco.
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — coordinatore ad alto livello sicuro per il flusso schede del pick-and-place OpenPnP.
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — barriera di coordinamento sicura per stampanti 3D Moonraker/Klipper, con comandi di lavoro reali e controllati.
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — coordinatore di sicurezza con un vero trasporto ROS 2 rclpy, importato in modo lazy.
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — barriera di coordinamento per UAV dotati di fotocamera, con un vero mittente di comandi MAVLink.

*Piattaforma Strumenti URTC*
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — strumento desktop con GUI per il flashing delle schede URTC, CAN-OTA più SWD/JTAG a chip intero.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — alternativa basata su browser a URTC-TESTER tramite la Web Serial API, senza installazione locale.

*Nodo IA Visione (Hailo-8)*
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — hub di integrazione per la pipeline di visione Hailo-8, con un vero controllo di prontezza hardware per fase.
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — generatore reale di pipeline GStreamer + config MediaMTX, con una vera barriera di integrazione HailoRT.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — vera legge di correzione Position-Based Visual Servoing, con cancello di sicurezza sullo stato di zona a monte.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — vero controllo di violazione zona e richiesta E-STOP, con imposizione della freschezza di calibrazione.

*Nodo IA Cognitivo (Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — hub di integrazione per la pipeline cognitiva Hailo-10 (orchestrazione LLM/VLA/voce).
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — vera codifica/decodifica di token d'azione e generazione di traiettoria per un modello Vision-Language-Action.
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — vero front-end vocale (VAD + parser di intenti) con un relay verso Watch limitato e soggetto a conferma.
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — vera scomposizione dei task basata su regole e recupero semantico degli errori sui codici errore MCU.
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — vera ricerca documentale TF-IDF (solo libreria standard) sui documenti Markdown di questo ecosistema.

*Orchestrazione e Sciame*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — hub di integrazione con un vero contratto di health-report gRPC/Protobuf e una macchina a stati di missione.
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — vera coda di lavori basata su priorità con deduplicazione, su una vera API HTTP.
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — vero watchdog di salute della flotta basato su gRPC, con retry/backoff e rilevamento di discrepanza d'identità.
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — vero pianificatore di percorsi 3D basato su RRT, con vera validazione delle collisioni ostacolo/spazio di lavoro.
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — vera sincronizzazione di stato CRDT LWW-Element-Map, con property test per la convergenza multi-cella.

*Gemello Digitale e Simulazione*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — hub di integrazione per il motore di gemello digitale, con un vero contratto di sincronizzazione per compatibilità di versione.
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — vero interblocco di sicurezza hardware-in-the-loop che instrada i comandi tra simulazione e hardware reale.
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — vera cinematica diretta e validazione dei limiti articolari su un vero sottoinsieme URDF.
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — vero generatore procedurale di scene 2D con esportazione di annotazioni YOLO/COCO.

*Dati e Analisi*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — vero archivio di serie temporali basato su sqlite3, con una vera API HTTP di ingestione/query.
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — vero rilevatore di anomalie FFT + baseline statistica, con monitoraggio della deriva.
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — vero calcolo OEE/disponibilità sullo storico di DATALAKE, con esportazione CSV riproducibile.
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — vera pipeline di ingestione CAN/WebSocket verso DATALAKE, con deduplicazione per sequenza.

*Gateway Industriale*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — hub di integrazione che inoltra ai protocolli industriali, con un vero livello di allowlist dei comandi/backpressure.
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — vero spazio di indirizzi OPC-UA, verificato con una vera sessione client del protocollo binario.
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — vero broker MQTT con autenticazione opzionale per client e ACL sui topic.
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — veri endpoint XML `/probe` e `/current` di MTConnect, con output in modalità degradata.

*Strumenti Complementari e Operazioni dell'Ecosistema*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — pannelli Smart Summaries e Anomaly Highlighting su DATALAKE/ANOMALY-DETECTOR, con un fallback statistico onesto.
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — CLI di flotta con un vero e stabile contratto di exit-code, un client live reale della stessa API di HYDRA-UMC-SERVER.
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — app companion WearOS con avvisi aptici reali e un relay vocale verso il telefono abbinato.
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — firmware per un rack di montaggio schede con decodifica reale dell'ID utensile e logica di preriscaldamento Smart Idle.
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — strumento amministrativo desktop che scopre, clona e aggiorna ogni repository di questo ecosistema.
- **[HYDRA-UMC-OS-REBUILDER](https://github.com/JuanenRac/HYDRA-UMC-OS-REBUILDER)** — strumento desktop Windows/Linux che costruisce un'immagine della CM5 pronta da scrivere, precaricata con le versioni più aggiornate dell'ecosistema, con configurazione di primo avvio Wi-Fi/utente/SSH in stile Raspberry Pi Imager.


---

## 📚 Documentazione e Comunità

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — stack tecnologico e linee guida di codifica per una pull request.
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** — gli standard di comportamento attesi in questa comunità.
- **[SECURITY.md](SECURITY.md)** — come segnalare una vulnerabilità, e le reali aree di attenzione sulla sicurezza di questo progetto.
- **[SUPPORT.md](SUPPORT.md)** — dove porre domande e segnalare bug.
- **[LICENSE.md](LICENSE.md)** — la licenza propria di questo progetto.

## 👤 AUTORE
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com
📺 [youtube.com/@electrohobby3d](https://youtube.com/@electrohobby3d)

## 📜 LICENZA
GPL-3.0 - Vedi LICENSE per i dettagli.
