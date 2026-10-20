# Backlog

Sammlung offener Ideen und Lücken, grob priorisiert. Aufwand: S (Stunden),
M (1 bis 2 Tage), L (mehrere Tage). Nichts davon ist zugesagt.

Legende Machbarkeit: ✅ mit der dokumentierten API machbar, ⚠️ nur teilweise
oder mit Annahmen, ❌ ohne Hilfe von Luke Roberts nicht machbar.

## 1. Fundament: was für ein solides Repo noch fehlt

| # | Punkt | Warum | Aufwand |
| --- | --- | --- | --- |
| R1 | **Test an echter Hardware** (Model F und Luvo, verschiedene Firmware, ESPHome Proxy, Shelly, USB Adapter) | Bisher nur gegen eine simulierte Lampe getestet. Größtes Risiko für Vertrauen und Bewertungen. Beta Tester über Forum suchen. | M |
| R2 | **Erstes Release taggen** (`v0.2.0`) und danach regelmäßig releasen | HACS zeigt Updates nur für Releases. Release Workflow ist schon da. | S |
| R3 | **Aufnahme in HACS Default** | Ohne Default Repo muss jeder die URL kennen. Voraussetzungen: Releases, Beschreibung und Topics im Repo, gültige `hacs.json`, Brand Bilder, grüne HACS Action. PR an `hacs/default`. | S |
| R4 | **Repo Metadaten**: Beschreibung, Topics (`home-assistant`, `hacs`, `bluetooth`, `luke-roberts`, `smart-lamp`), Website Link, Social Preview Bild | Auffindbarkeit auf GitHub und Google | S |
| R5 | **Screenshots / kurzes GIF in der README** (Einrichtung, Tile Card, Szenen Dropdown) | Der erste Eindruck entscheidet, ob jemand installiert | S |
| R6 | **Originallogo** mit Freigabe von Luke Roberts in `brand/` | Wiedererkennung in der HA Oberfläche | S |
| R7 | **Testabdeckung messen** (pytest-cov, Badge) und Lücken schließen (button, select, sensor, diagnostics, Options Flow Pfade) | Qualitätssignal, schützt vor Regressionen | M |
| R8 | **Typprüfung** mit mypy im CI | Fängt Fehler früh, Voraussetzung für HA Core | M |
| R9 | **pre-commit** Konfiguration (ruff, json, yaml) | Einheitlicher Code bei Beiträgen anderer | S |
| R10 | `CONTRIBUTING.md`, `SECURITY.md`, Code of Conduct, Labels, PR Vorlage | Macht Beiträge von außen einfacher | S |
| R11 | **Release Drafter** oder Changelog aus PR Labels | Weniger Handarbeit pro Release | S |
| R12 | **Mindestversion HA prüfen**: `hacs.json` sagt 2025.2, getestet wird gegen 2026.2. Matrix im CI oder Mindestversion anheben | Ehrliche Kompatibilitätsangabe | S |
| R13 | **Integration Quality Scale** abarbeiten (Bronze bis Gold): Reconfigure Flow, Repairs, `icons.json`, Entity Kategorien, Unload sauber, Diagnostics | Messlatte von HA, langfristig Weg Richtung Core | L |
| R14 | Weitere Übersetzungen (fr, nl, it, es) | Luke Roberts Kunden sitzen vor allem in DACH, aber nicht nur | S je Sprache |

## 2. Marktdurchdringung

| # | Punkt | Aufwand |
| --- | --- | --- |
| M1 | Vorstellungsthread im Home Assistant Community Forum (Kategorie *Share your Projects*) | S |
| M2 | Beitrag im deutschen simon42 Forum und auf r/homeassistant | S |
| M3 | Luke Roberts selbst informieren: Hinweis im Support, Newsletter oder in der App FAQ wäre der größte Hebel | S |
| M4 | Bestehende Nutzer der ESPHome Lösung gezielt auf die Integration hinweisen (README dort, Release Notes) | S |
| M5 | Blueprints veröffentlichen (Sonnenaufgang Wecker, Szene per Taster, Anwesenheit) mit My Home Assistant Import Button | M |
| M6 | Kurze Doku Seite (GitHub Pages) mit FAQ: Proxy Einrichtung, Sicherheitscode, Fehlersuche | M |
| M7 | Langfristig: Aufnahme in HA Core. Bringt die meiste Reichweite, erfordert aber eine eigene PyPI Bibliothek für das Protokoll (`protocol.py`, `ble.py`, `cloud.py` auslagern) und Quality Scale | L |

## 2b. SEO und Repo Einstellungen

Stand 2026-10-20. Die GitHub Suche nach "luke roberts" liefert 26 Repos,
davon mindestens 7 Home Assistant Integrationen (u. a.
`tpulatha/pyLukeRoberts_hacs`, `melikeoflu/luke_roberts`,
`NilsHempel/ha-luke-roberts-luvo`, `sebpiller/ha-luke-roberts-lampf`,
`kneirinck/hacs-luke-roberts`). Keine hat nennenswert Sterne, der Platz ist
also noch offen. Das größte Repo zum Thema ist `martgras/LukeRobertsControl`
(19 Sterne, MQTT Gateway).

| # | Punkt | Aufwand |
| --- | --- | --- |
| S1 | **Beschreibung** (Settings, About): `Home Assistant integration for Luke Roberts Model F & Luvo smart lamps (HACS): local Bluetooth control via ESPHome/Shelly proxies, scenes, uplight colour, cloud fallback`. Google nimmt sie als Titel bzw. Snippet. Wichtig sind *Model F*, *Luvo*, *HACS* und *ESPHome*, die fehlen bisher. | S |
| S2 | **Topics** ersetzen, siehe unten | S |
| S3 | **Website** im About Feld: der My Home Assistant Link zum Installieren über HACS (`https://my.home-assistant.io/redirect/hacs_repository/?owner=3DJupp&repository=lukeroberts-homeassistant&category=integration`), später der Forum Thread | S |
| S4 | **Social Preview** hochladen: `docs/social-preview.png` (Settings → General → Social preview). Wird bei Links in Forum, Reddit, Signal usw. angezeigt. | S |
| S5 | **Release Titel mit Keywords**, z. B. "0.2.0: Luke Roberts account and auto linking". Releases werden indexiert. | S |
| S6 | **Domain Konflikt prüfen**: mehrere der anderen Integrationen nutzen vermutlich ebenfalls die Domain `luke_roberts`. Zwei davon lassen sich nicht parallel installieren, und für HACS Default kann das zur Rückfrage führen. Domains der Konkurrenz prüfen, notfalls in der README darauf hinweisen. | S |
| S7 | **Backlinks**: Hinweis im ESPHome Repo (schon da), Forum Thread, simon42, ggf. Eintrag in "awesome-home-assistant" | S |
| S8 | **Vergleichstabelle** zu den anderen Luke Roberts Integrationen in der README (Proxy Support, Szenen Namen, Cloud, Übersetzungen). Fair formulieren, nur belegbare Punkte. | S |

### Topics: Challenge

Aktuell: `bluetooth-le`, `bluetooth-proxy`, `hacs`, `hacs-integration`,
`home-assistant`, `homeassistant-custom-component`, `luke-roberts`.

* `bluetooth-le` ist ein seltenes Topic. Gesucht wird `ble` und
  `bluetooth-low-energy`, beide ersetzen es.
* Es fehlen die Schreibvarianten, über die HA Nutzer tatsächlich browsen:
  `homeassistant`, `home-assistant-integration`,
  `home-assistant-custom-component`, `custom-integration`.
* Es fehlen Marke und Produkt in anderer Schreibweise: `lukeroberts`, `luvo`.
  `model-f` lieber nicht, das Topic gehört den IBM Tastaturen.
* Es fehlen die Ökosysteme, über die Leute kommen: `esphome`, `shelly`.
* Allgemeine Kategorien: `smart-lighting`, `smart-home`, `home-automation`.
* `python` bringt nichts, die Sprache erkennt GitHub selbst.

Vorschlag, 19 von maximal 20:

```
home-assistant homeassistant home-assistant-integration
home-assistant-custom-component homeassistant-custom-component
hacs hacs-integration custom-integration
luke-roberts lukeroberts luvo
ble bluetooth-low-energy bluetooth-proxy esphome shelly
smart-lighting smart-home home-automation
```

## 3. Features

### F1 Firmware: Anzeige und Prüfung

* **Installierte Firmware anzeigen** ✅ (S): wird schon aus dem Device
  Information Service gelesen und im Gerät angezeigt. Zusätzlich als `update`
  Entity mit `installed_version`, damit sie im Update Dashboard auftaucht.
* **Prüfen ob neue Firmware verfügbar ist** ⚠️ (M): es gibt keine
  dokumentierte Quelle für die neueste Version. Prüfen, ob `GET /lamps` in der
  Cloud eine Firmwareangabe liefert. Alternative: Versionsliste im Repo pflegen
  und per Hinweis (Repair Issue) melden, wenn die Lampe älter ist als z. B.
  1.1.1 (Auto Disconnect) oder 1.0.7 (fehlende Befehle).
* **Firmware über HA installieren** ❌: die Lampe hat einen eigenen Firmware
  Update Service, der aber nicht dokumentiert ist, und die Firmware Dateien
  sind nicht öffentlich. Ein fehlerhaftes Update kann die Lampe unbrauchbar
  machen. Nur mit Spezifikation von Luke Roberts angehen. Bis dahin: Update
  Entity verweist auf die App.

### F2 Szenen Builder

Grenzen der API: Szenen werden in der App gebaut und in der Lampe
gespeichert. Die API kann Szenen nur auswählen und ihren Namen lesen, nicht
anlegen oder ändern. Das Uplight lässt sich per *Immediate Light* nur als
Ganzes einfärben, nicht die 16 Segmente einzeln. Das Downlight nur mit
Farbtemperatur und Helligkeit, nicht die 84 Spots einzeln.

Machbar ✅ (M bis L):

* **HA eigene Szenen** ("virtuelle Szenen"): Basis Szene der Lampe +
  Uplight Farbe/Helligkeit + Downlight Kelvin/Helligkeit, gespeichert in der
  Integration (Store) und als Effekte bzw. im Szenen Dropdown angeboten.
  Aktionen `save_scene` / `delete_scene`.
* **Oberfläche**: Options Flow Schritt "Szene anlegen" mit Farbwähler, oder
  eine kleine Custom Lovelace Card mit Live Vorschau (sendet Immediate Light
  während man schiebt).
* **Hinweis in der Doku**: Änderungen gehen beim Szenenwechsel in der App
  oder per Click Detection verloren, das ist eine Eigenschaft der Lampe.

### F3 Weitere Features

| # | Feature | Machbarkeit | Aufwand |
| --- | --- | --- | --- |
| F3.1 | **Zweite Light Entity "Uplight"** mit HS Farbe (über Immediate Light), damit Farbe direkt in Dashboards, Szenen und Sprachassistenten geht | ✅ | M |
| F3.2 | **Übergänge** (`transition`): Helligkeit in Schritten faden, emuliert über mehrere Befehle | ✅ | M |
| F3.3 | **Lampen Szenen als HA `scene` Entities**, damit Assist / Alexa / Google sie direkt aufrufen können | ✅ | S |
| F3.4 | **Signalstärke (RSSI) und "verbunden über" Sensor** (welcher Adapter oder Proxy) | ✅ | S |
| F3.5 | **Repair Issues**: Sicherheitscode gesetzt (Status `FC`), alte Firmware, Lampe lange nicht gesehen, Cloud Key abgelehnt | ✅ | M |
| F3.6 | **Reconfigure Flow**: Bluetooth Adresse ändern (Lampe getauscht) ohne Entities zu verlieren | ✅ | S |
| F3.7 | **`icons.json`** für Entity und Aktions Icons | ✅ | S |
| F3.8 | Option **Cloud Abfrageintervall** und dauerhafte Bluetooth Verbindung (Linger "unbegrenzt") | ✅ | S |
| F3.9 | **Adaptive Lighting / zirkadian**: Doku und Test mit der Adaptive Lighting Integration, ggf. Kelvin Steuerung ohne Szenenwechsel | ✅ | S |
| F3.10 | **Sonnenaufgang Wecker** als eingebaute Aktion (Uplight warm rot → Downlight hell über N Minuten) | ✅ | M |
| F3.11 | **Szenen automatisch neu lesen** in Abständen oder beim Wiederauftauchen der Lampe, damit Änderungen aus der App ankommen | ✅ | S |
| F3.12 | **Mehrere Lampen gleichzeitig** schalten ohne Verzögerung (parallele Verbindungen über verschiedene Proxies) | ⚠️ hängt an Proxy Slots | M |
| F3.13 | **Sicherheitscode unterstützen** (Lampen, die lokal `FC` antworten) | ❌ Protokoll nicht dokumentiert, bei Luke Roberts anfragen | ? |
| F3.14 | **Zustand der Lampe lesen** statt angenommenem Zustand | ❌ lokal nicht vorgesehen, Cloud Endpunkt `state` undokumentiert | ? |
| F3.15 | **Click Detection als Ereignis** (Tippen auf die Lampe als Trigger) | ❌ API meldet das nicht | ? |

## 4. Fragen an Luke Roberts

Einmal gesammelt nachfragen, beantwortet sie mehrere ❌ Punkte auf einmal:

1. Freigabe des Logos für die HA Oberfläche (R6)
2. Spezifikation des Firmware Update Service oder eine Quelle für die neueste
   Firmware Version (F1)
3. Wie Drittanbieter mit gesetztem Sicherheitscode arbeiten können (F3.13)
4. Ist `GET /lamps/{id}/state` stabil und welches Format hat die Antwort (F3.14)
5. Liefert `GET /lamps` Seriennummer und Firmware, und entspricht die
   Seriennummer der aus dem Bluetooth Device Information Service
6. Gibt es einen Weg, Szenen über die API anzulegen (F2)

## 5. Vorschlag Reihenfolge

1. R1, R2, R4, R5 (bevor irgendwer davon erfährt)
2. R3, M1 bis M4 (Reichweite)
3. F3.1, F3.3, F3.5, F1 Anzeige (sichtbarer Mehrwert, wenig Risiko)
4. F2 Szenen Builder
5. R13 und M7 (Weg Richtung Core)
