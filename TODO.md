# TODO – UpservX

Diese Datei enthält nur noch offene Arbeiten, die sich aus dem aktuellen
Repository-Stand ableiten lassen. Allgemeine Ideen stehen hinter konkreten
Fehlern, Sicherheitslücken und fehlenden Qualitätssicherungen zurück.

**Letzter vollständiger Repository-Audit:** 5. August 2026

**Geprüfter Stand:** `0.6.0`
**Prioritäten:** P0 = Release-Blocker, P1 = vor stabilem Produktivbetrieb,
P2 = nächster Funktionsausbau, P3 = langfristige/Enterprise-Roadmap

## P0 – Release-Blocker

### Autorisierung und Vertrauensgrenzen

- [ ] Die Backend-Autorisierung vollständig korrigieren und mit Negativtests
  absichern.
  - `/security/*` ist derzeit nicht als Admin-Bereich eingestuft. Dadurch kann
    jeder angemeldete Benutzer unter anderem Paket-Upgrades auslösen und
    Fail2Ban-Sperren aufheben.
  - `/cluster/*`, `/cluster/ha/*` und `/vm-networks/*` fallen ebenfalls durch
    die aktuelle Standardfreigabe. Cluster-Erstellung, Replikation, Failover
    und Netzwerkänderungen müssen explizite Rollen erfordern.
  - Berechtigungen nicht nur über URL-Präfixe, sondern pro Route und Aktion
    definieren; lesende und verändernde Operationen getrennt behandeln.
  - Tests für alle Rollen, API-Schlüssel, Cluster-Principals und unbekannte
    Routen ergänzen. Standardverhalten muss „deny by default“ sein.

- [ ] Interne Cluster- und HA-Endpunkte wirklich authentifizieren.
  - Die Middleware überspringt Heartbeat, Vote, Master-Update,
    VIP-Owner-Update und Config-Sync; die Routen selbst prüfen aktuell keinen
    Cluster-Schlüssel.
  - Nachrichten signieren beziehungsweise mTLS verwenden, Replay-Schutz und
    Zeitfenster ergänzen sowie Schlüsselrotation ermöglichen.
  - Den Cluster-Token nicht mehr über `/cluster/info` an jeden angemeldeten
    Benutzer ausgeben.
  - Inter-Node-Verkehr nicht unverschlüsselt über `http://` betreiben.

- [ ] Geheimnisse und Sitzungen härten.
  - Backup-Konfiguration darf Passwörter nicht über Debug-Ausgaben loggen;
    Vorschauen von Verschlüsselungsschlüsseln und Ciphertext entfernen.
  - Verschlüsselung muss bei Fehlern geschlossen abbrechen. Niemals Klartext
    als stillen Fallback speichern oder zurückgeben.
  - Für die 2FA-Anmeldung kein Linux-Passwort mehr in
    `/etc/upservx/login_tokens.json` zwischenspeichern; Benutzername und
    erfolgreich bestandene erste Authentifizierungsstufe reichen aus.
  - Session-Cookie für HTTPS mit `Secure`, passendem `SameSite`-/Domain-/Path-
    Verhalten und klarer Ablauf-/Widerrufsstrategie versehen.
  - Den einzelnen globalen API-Key durch widerrufbare, gehashte und
    rollen-/scope-gebundene API-Tokens ersetzen.
  - Dateirechte aller Dateien unter `/etc/upservx` zentral definieren und testen.

### Prozessmodell und persistenter Zustand

- [ ] Das Backend-Prozessmodell mit `uvicorn --workers 4` korrigieren.
  - Rate-Limits, WebSocket-Tickets, HA-Manager, Metrikzustand und verschiedene
    globale Manager leben derzeit nur im Speicher eines Workers.
  - Ein Ticket kann deshalb in Worker A erzeugt und in Worker B abgelehnt
    werden; Rate-Limits lassen sich pro Worker umgehen.
  - Entweder vorerst einen Worker erzwingen oder alle gemeinsam benötigten
    Zustände in einen transaktions- und nebenläufigkeitssicheren Store verlegen.
  - Prozesslokale Locks bei gemeinsam beschriebenen JSON-Dateien durch echte
    Cross-Process-Synchronisation und atomare Updates ersetzen.

- [ ] Langlebige Arbeiten aus HTTP- und Worker-Prozessen herauslösen.
  - Backups, Replikationen, Exporte, Scans und Updates als persistente Jobs mit
    Status, Retry, Abbruch, Timeout und Wiederaufnahme ausführen.
  - Ein Neustart darf laufende Arbeit nicht unbemerkt verlieren oder dauerhaft
    den Status `running` hinterlassen.

### Installation, Dienstrechte und Updates

- [ ] Ein eindeutiges Privilegienmodell festlegen und installieren.
  - Der systemd-Dienst läuft je nach Installationsart als normaler Benutzer oder
    root, während Backend-Funktionen gleichzeitig `/etc`, Netzwerk, Firewall,
    Benutzer, Datenträger, libvirt, Docker und systemd verändern wollen.
  - Einen dedizierten Dienstbenutzer und eng begrenzte privilegierte Helfer,
    Gruppen beziehungsweise sudoers-Regeln einrichten.
  - Docker-, LXD-, libvirt-/KVM- und Dateiberechtigungen beim Installieren
    reproduzierbar setzen und mit einem Post-Install-Smoke-Test prüfen.

- [ ] Den Updatepfad neu bauen.
  - `install.sh` kopiert ohne `.git` nach `/opt/upservx`, `update.sh` versucht
    dort aber `git pull` auszuführen.
  - Das Update wird vom laufenden Dienst gestartet und stoppt genau diesen
    Dienst; mit dem üblichen systemd-KillMode kann der Updateprozess dabei
    selbst beendet werden.
  - Update außerhalb des Webdienstes ausführen, signierte/versionierte Artefakte
    verwenden, Konfiguration sichern, atomar umschalten, Health-Check und
    Rollback ergänzen.
  - Fehlerhafte Exit-Codes müssen als Fehler gemeldet werden; derzeit antwortet
    die API auch bei einem fehlgeschlagenen Skript mit „update completed“.

- [ ] Den Installer sicher und minimal machen.
  - Das globale Entfernen von `pam_lastlog.so` aus PAM-Dateien unterlassen.
  - Heruntergeladene K3s-/Repository-Skripte und Schlüssel verbindlich prüfen;
    keine ungeprüften Remote-Skripte ausführen.
  - K3s, LXD, PostgreSQL, FTP/vsftpd, OpenVPN, ZFS und weitere große Komponenten
    als optionale Profile statt immer als Pflichtpakete installieren.
  - `npm ci` und reproduzierbare Python-Abhängigkeiten statt veränderlicher
    Installationen verwenden.
  - Frontend und Backend als getrennte systemd-Units mit Readiness-/Liveness-
    Checks betreiben.

- [ ] Die noVNC-Quelle im Repository reparieren.
  - `upservx/public/novnc` ist ein Gitlink, aber es gibt keine passende
    `.gitmodules`-Zuordnung.
  - Entweder korrektes Submodul eintragen oder noVNC ausschließlich als
    installierte/geprüfte Abhängigkeit beziehen und den Gitlink entfernen.

### Backup-System funktionsfähig machen

- [ ] Eine einzige Datenquelle für Backup-Server verwenden.
  - Erstellen, Auflisten und Löschen arbeiten derzeit mit
    `backup_servers.json`; Aktualisieren und Verbindungstest greifen auf die
    SQLite-Tabelle `backup_servers` zu.
  - Ein Schema auswählen, bestehende Daten migrieren und CRUD, Jobs,
    Zugangsdaten sowie Fremdschlüssel durchgehend darüber abwickeln.
  - Statuswerte und Modelle vereinheitlichen (`active` versus
    `connected`/`disconnected`/`error`).

- [ ] Geplante Backups ausführbar machen.
  - Der Cron-Manager zeigt auf `lib/execute_backup.py`, die Datei liegt jedoch
    unter `handlers/execute_backup.py`.
  - Cron verwendet `/usr/bin/python3` statt des installierten UpservX-Venvs.
  - Änderungen an Zeitplan und Aktivstatus müssen vorhandene Cron-Einträge
    aktualisieren beziehungsweise entfernen.
  - Cron-Ausführung, manuelle Ausführung und UI-Trigger müssen denselben
    getesteten Codepfad verwenden.

- [ ] Backup-Lebenszyklus vervollständigen.
  - Wiederherstellen für Datei-, Container- und VM-Backups als sichere API- und
    UI-Workflows implementieren; Tar-Extraktion gegen Traversal, Symlinks und
    Überschreiben absichern.
  - Beim Löschen einer Backup-Instanz auch das lokale beziehungsweise entfernte
    Archiv behandeln; aktuell wird nur der Datenbankeintrag gelöscht.
  - `retention_days` tatsächlich auf Archive und Metadaten anwenden.
  - Den `compression`-Schalter im produktiven Ausführungspfad respektieren.
  - Prüfsummen, automatische Integritätsprüfung und regelmäßige Test-Restores
    ergänzen.
  - VM-Konsistenz über libvirt-Snapshots/QEMU Guest Agent sicherstellen statt
    große laufende Disks lediglich zu suspendieren und zu tar-en.

### Defekte API-Verträge und Cluster-Synchronisation

- [ ] Frontend, CLI und Backend gegen einen gemeinsamen API-Vertrag abgleichen.
  - Das Frontend ruft `/settings/generate-api-key` auf, das Backend bietet
    `/settings/api-key` an.
  - Der TypeScript-Client enthält `/backup/servers/{id}/info` und komplette
    `/ssh-keys/*`-APIs, für die keine Routen registriert sind.
  - Die CLI bietet Container-`restart` und `inspect`, obwohl entsprechende
    Backend-Routen fehlen.
  - `upservx backup create` sendet kein gültiges `BackupJobCreate`-Objekt und
    kann so keinen Job erstellen.
  - CLI-2FA-Anmeldung implementieren oder klar als nicht unterstützt behandeln.
  - OpenAPI als Quelle für generierte TypeScript-/CLI-Typen und Contract-Tests
    verwenden.

- [ ] Container-Synchronisation im Cluster fertigstellen oder bis dahin aus der
  UI entfernen.
  - Der Sync-Manager sendet an `/containers/deploy`; diese Route existiert nicht.
  - Das Auslesen der Service-Konfiguration ist ausdrücklich nur ein Platzhalter.
  - „Migration“ löscht nur lokalen Sync-Zustand und stoppt den Quellcontainer
    nicht.
  - Teilfehler werden nicht aggregiert; `/cluster/sync/execute` kann Erfolg
    melden, obwohl keine Replikation funktioniert hat.
  - Volumes, Secrets, Netzwerke, Portkonflikte, Images und Rollback korrekt
    übertragen beziehungsweise behandeln.

### App Store korrigieren

- [ ] Alle Templates durch einen verbindlichen Schema- und Compose-Test bringen.
  - `mailcow/docker-compose.yml` ist syntaktisch ungültig.
  - `apache-kafka/` ist leer, obwohl Kafka in Release Notes als vorhanden gilt.
  - Home Assistant, Paperless-ngx und Uptime Kuma verwenden Objektlisten für
    `ports`, `volumes` und `environment`; das aktuelle Frontend erwartet dort
    `string[]` beziehungsweise ein String-Objekt und kann die Detailansicht
    nicht zuverlässig rendern.
  - Ein JSON-Schema festlegen und alle 61 vorhandenen vollständigen Templates
    darauf migrieren.

- [ ] Aus „Install“ eine echte, sichere Installation machen.
  - Der Handler kopiert derzeit nur das Template in ein Projektverzeichnis und
    startet keinen Compose-Stack.
  - Umgebungsvariablen aus `app.json` im Installationsdialog editierbar machen,
    Required-Felder prüfen und Secrets automatisch sicher generieren.
  - Harte Standardpasswörter und `changeme`-/`admin`-Zugangsdaten aus den
    produktiven Compose-Dateien entfernen.
  - Installation transaktional ausführen: Compose validieren, Images beziehen,
    starten, Health-Checks abwarten und bei Fehlern zurückrollen.
  - Benutzerdefinierte Projektnamen beim Installationsstatus korrekt zuordnen.
  - Image-Versionen bewusst pinnen und einen getesteten Updatepfad für Apps
    definieren, statt überall unkontrolliert `latest` zu verwenden.

### Qualitätssicherung wieder verbindlich machen

- [ ] Den Frontend-Lint-Befehl für Next.js 16 reparieren.
  - `npm run lint` verwendet das entfernte `next lint`; direkter ESLint-Aufruf
    funktioniert.
  - `eslint-config-next` auf dieselbe Hauptversion wie `next` bringen.

- [ ] CI-Prüfungen als echte Gates konfigurieren.
  - Backend-Tests und beide Linter dürfen Fehler nicht mehr mit
    `continue-on-error` oder `|| echo` verschlucken.
  - Python-Syntaxprüfung rekursiv auf `api/`, `handlers/`, `lib/`, CLI und Tests
    anwenden statt nur auf `*.py` im Wurzelverzeichnis.
  - App-JSON-Schema, `docker compose config`, Shell-Syntax, OpenAPI-Contracts,
    Frontend-Build und CLI-Tests in CI aufnehmen.
  - Für lokale Entwicklung einen dokumentierten, reproduzierbaren Test-Befehl
    bereitstellen; das vorhandene Root-`.venv` enthält aktuell weder pip noch
    importierbares pytest.

## P1 – Stabilität vor produktivem Einsatz

### Tests und reale Integrationen

- [ ] Backend-Testabdeckung auf alle kritischen Module erweitern: Backup,
  Cluster/HA, VM/LXC/KVM, App Store/Compose, Firewall, Netzwerk, Reverse Proxy,
  Security, Settings/VPN, Benachrichtigungen und Updates.
- [ ] Veraltete Tests auf Bearer-/Cookie-Authentifizierung umstellen; Fixtures
  dokumentieren noch Basic Auth, obwohl die Middleware nur Bearer-Tokens nutzt.
- [ ] Echte Systemtests in isolierten VMs ergänzen:
  - Neuinstallation und Update auf unterstützten Debian-/Ubuntu-Versionen
  - Docker und Compose, LXD/LXC, KVM/libvirt und noVNC
  - Backup plus Restore lokal und über SSH
  - Zwei- und Drei-Knoten-Cluster inklusive Netzwerkausfall und Split-Brain
  - Firewall-, Netzwerk- und Datenträgeroperationen mit sicherem Rollback
- [ ] Frontend-Komponenten-, Accessibility- und End-to-End-Tests ergänzen.
- [ ] CLI-Unit- und Contract-Tests für jeden dokumentierten Befehl ergänzen.

### Eingaben, Ressourcen und Fehlerbehandlung

- [ ] Uploads und Downloads streamen und begrenzen.
  - ISO-Upload, VPN-/Logo-/Banner-Upload und Cluster-Upload haben teilweise
    keine Größenlimits und lesen komplette Dateien in den Speicher.
  - Cluster-Export verwendet `capture_output` für komplette Container- und
    Image-Archive; große Ressourcen müssen direkt auf Disk/Storage streamen.
  - Quotas, freie Speicherkontrolle, Timeouts, Abbruch und Bereinigung
    unvollständiger Dateien ergänzen.
- [ ] ISO-URL-Download gegen DNS-Rebinding, Redirects, IPv6/private Netze,
  fehlende Timeouts und unbegrenzte Dateigröße härten.
- [ ] Bild-Uploads anhand des tatsächlichen Dateiinhalts prüfen, SVG entweder
  sanitizen oder verbieten und gespeicherte Dateien mit sicheren Headern
  ausliefern.
- [ ] Destruktive Aktionen serverseitig validieren: Systemdisk, Root-Dateisystem,
  aktive Netzwerkschnittstelle, Management-Zugang und fremde Pfade dürfen nicht
  versehentlich formatiert, ausgehängt oder abgeschnitten werden.
- [ ] Breite `except Exception`-/`pass`-Blöcke durch definierte Fehler,
  strukturierte Logs und verwertbare API-Fehler ersetzen.
- [ ] Debug-Ausgaben im Backup-/Cluster-Code entfernen und einheitliches,
  redigiertes Logging mit Rotation und Audit-Ereignissen verwenden.

### Frontend und Bedienung

- [ ] Den globalen `window.fetch`-Monkey-Patch durch einen zentralen API-Client
  ersetzen, der Cookies, Fehler, Timeouts, Abbruch und 401-Verhalten konsistent
  behandelt.
- [ ] Lade-, Leer-, Teilfehler- und Retry-Zustände in allen Modulen einheitlich
  umsetzen; Fehler nicht nur in der Browser-Konsole verwerfen.
- [ ] Lange Operationen über Jobfortschritt statt blockierende Requests führen.
- [ ] Sicherheitskritische Aktionen mit konkreter Auswirkung, Ziel und
  Wiederherstellbarkeit bestätigen lassen.
- [ ] Die fest eingetragene Entwicklungs-IP in `next.config.ts` entfernen und
  erlaubte Origins konfigurierbar machen.

### Datenmodelle und Wartbarkeit

- [ ] Persistenz konsolidieren. Aktuell werden SQLite, viele JSON-Dateien,
  `/etc/crontab` und Prozessspeicher parallel genutzt; Transaktionen,
  Migrationen, Backups und Ownership sind dadurch uneinheitlich.
- [ ] Unbenutzte beziehungsweise widersprüchliche DB-Abhängigkeiten und
  Dokumentationsbehauptungen zu PostgreSQL/SQLAlchemy/Alembic entfernen oder
  eine echte, versionierte Datenbankmigration implementieren.
- [ ] Große Module (`api/cluster.py`, `handlers/vms.py` und mehrere sehr große
  React-Komponenten) in klar getestete Domänen aufteilen.
- [ ] Pydantic-v2-APIs (`model_dump`) konsistent verwenden und Eingabemodelle mit
  Enums, Limits, Pfad-/Namensvalidierung sowie aussagekräftigen Constraints
  versehen.
- [ ] Hintergrundzustände, temporäre Exporte, Uploads und alte Progress-Daten
  regelmäßig und nachvollziehbar bereinigen.

### Dokumentation und Repository-Hygiene

- [ ] Dokumentation mit dem tatsächlichen Code synchronisieren.
  - Auth-Dokumentation beschreibt teilweise noch Basic Auth und Base64-Cookies.
  - Viele Endpoint-Tabellen, Dateipfade, Modellnamen und Funktionsnamen stimmen
    nicht mit den registrierten Routern überein.
  - Architektur behauptet PostgreSQL/Alembic und eine alte Dateistruktur, obwohl
    der aktive Code überwiegend JSON und SQLite nutzt.
  - App-Store-Dokumentation nennt 49 Apps; vorhanden sind 61 vollständige
    Templates plus ein leeres Kafka-Verzeichnis.
  - `upservx/README.md` ist noch das generische Create-Next-App-README.
- [ ] Unterstützte Versionen eindeutig festlegen.
  - Der Code benötigt wegen `X | None` mindestens Python 3.10, README und Docs
    versprechen Python 3.8.
  - Installer/CI verwenden Node 20, README nennt Node 18; die Next.js-Angabe im
    Badge ist ebenfalls falsch.
- [ ] `.gitignore` um lokale Venvs, Laufzeit-Schlüsselverzeichnisse,
  Test-/Build-Caches und temporäre Backend-Daten ergänzen.
- [ ] Debug-/Hilfsskripte (`debug_backup_test.py`, `test_encryption.py`) entweder
  in echte Tests überführen oder aus dem Produktquellbaum entfernen.

## P2 – Nächster Funktionsausbau

### Virtuelle Maschinen

- [ ] Verwaltete VM-Templates und versionierte Images mit schnellem Rollout
  implementieren.
- [ ] Linked Clones zusätzlich zum vorhandenen vollständigen Clone unterstützen.
- [ ] Mehrere Netzwerkkarten pro VM, per-VM-Portweiterleitungen und
  Firewall-/Security-Profile ergänzen.
- [ ] QEMU Guest Agent integrieren: IP-/Hostname-Erkennung, geordnetes Shutdown,
  Filesystem-Freeze/Thaw und backup-konsistente Snapshots.
- [ ] Libvirt-Storage-Pools als eigenes Modell mit Kapazität, Auswahl,
  Berechtigungen und Lifecycle verwalten.
- [ ] Vorhandenes Cloud-init, Snapshots, Clone sowie OVA/OVF-Import/-Export mit
  verschiedenen Distributionen, Firmwaretypen, Multi-Disk-VMs und externen
  Hypervisoren interoperabel testen.

### Backup und Disaster Recovery

- [ ] Backup-Archive optional clientseitig beziehungsweise vor dem Upload
  verschlüsseln; Schlüsselrotation, Recovery-Key und dokumentierte
  Wiederherstellung vorsehen.
- [ ] Inkrementelle/deduplizierte Backups, Bandbreitenlimits und resumierbare
  Remote-Transfers implementieren.
- [ ] Aufbewahrungsregeln nach Anzahl, Alter und Speicherbudget sowie
  unveränderliche/offsite Ziele unterstützen.
- [ ] Einen vollständigen Disaster-Recovery-Ablauf für UpservX-Konfiguration,
  Benutzer, Cluster, Apps, Container und VMs dokumentieren und automatisiert
  testen.

### Netzwerk, Storage und Plattform

- [ ] Bonding, verwaltete Bridges, Open vSwitch und VXLAN/Overlay-Netze ergänzen.
- [ ] NFS/iSCSI und LVM-Thin als first-class Storage-Pools integrieren.
- [ ] Load-Balancer-Funktionalität klar trennen:
  - vorhandene Workload-Platzierung und Empfehlungen zuverlässig ausführen
  - optional HAProxy/Traefik-Datastore, Health-Checks, TLS und Sticky Sessions
    als echten Traffic-Load-Balancer bereitstellen
- [ ] Ressourcenpools, Quotas, Placement-/Anti-Affinity-Regeln und geplante
  Wartungsmodi ergänzen.

### Identitäten und UX

- [ ] LDAP/Active Directory sowie OIDC/SAML-SSO integrieren und externe Gruppen
  auf interne Rollen abbilden.
- [ ] Rollen feiner als Linux-Gruppen modellieren: read-only, operator,
  subsystem-admin und audit-only.
- [ ] Internationalisierung technisch einführen und danach vollständige
  Übersetzungen für Englisch und Deutsch bereitstellen; weitere Sprachen erst
  auf derselben Übersetzungsbasis ergänzen.
- [ ] Tastaturbedienung, Screenreader-Texte, Fokusführung, Kontrast und responsive
  Darstellung systematisch nach WCAG prüfen.
- [ ] Durchgängige Audit-Historie für Benutzer-, API- und Cluster-Aktionen mit
  Filter, Export und manipulationsgeschützter Aufbewahrung ergänzen.

## P3 – Langfristige Enterprise-Roadmap

- [ ] Quorum-basierter Cluster mit Fencing/STONITH und nachweisbarem
  Split-Brain-Schutz; bestehende eigene HA-Logik vorher klar als experimentell
  kennzeichnen.
- [ ] Live-Migration laufender VMs inklusive Shared-/Local-Storage-Behandlung.
- [ ] Ceph/RBD, Storage-Replikation und optional Erasure Coding integrieren.
- [ ] Automatische HA-Ressourcenwiederherstellung, Startreihenfolgen,
  Failover-Policies und Wartungsorchestrierung implementieren.
- [ ] Multi-Node-Upgrade mit Versionskompatibilitätsprüfung, gestaffeltem Rollout
  und automatischem Rollback entwickeln.
- [ ] Mandantenfähigkeit mit isolierten Ressourcen, Netzwerken, Secrets,
  Abrechnung/Quotas und delegierter Administration evaluieren.

## Definition of Done für den nächsten Release-Kandidaten

- [ ] Sauberer Clone hat keinen defekten Gitlink und baut reproduzierbar.
- [ ] `npm ci`, Frontend-Build, ESLint, Python-Lint, vollständige Backend-/CLI-
  Tests, Contract-Tests und alle Template-Validatoren laufen lokal und in CI
  ohne ignorierte Fehler durch.
- [ ] Installation und Update wurden auf mindestens einer unterstützten Debian-
  und Ubuntu-Version inklusive Rollback getestet.
- [ ] Keine Route mit Systemänderungsrechten ist für eine unberechtigte Rolle
  erreichbar; Cluster-interne Endpunkte sind authentifiziert und verschlüsselt.
- [ ] Backup lokal und über SSH wurde erstellt, verifiziert, wiederhergestellt
  und anhand der Retention-Regel gelöscht.
- [ ] App-Store-Installation startet einen validierten Stack ohne bekannte
  Standardpasswörter und meldet Health-/Rollback-Status korrekt.
- [ ] Dokumentierte API, CLI-Befehle, Versionen, Pfade und Voraussetzungen
  entsprechen dem ausgelieferten Code.

## Bereits vorhanden – nicht erneut als fehlend einplanen

Folgende Punkte aus der alten TODO sind im aktuellen Code grundsätzlich schon
vorhanden und benötigen Tests/Härtung statt einer Neuimplementierung:

- Cloud-init-User-Data bei der VM-Erstellung
- VLAN-Unterstützung und interne libvirt-Netze
- VM-Cloning, Snapshots sowie OVA/OVF-Import und -Export
- Linux-Gruppen-basierte Basisberechtigungen, API-Key und TOTP-2FA
- Grundlegende Cluster-, Replikations-, Placement- und HA/VIP-Oberflächen
- Lokale und SSH-basierte Backup-Grundfunktionen
- nftables-Firewall, Reverse Proxy, Zertifikate, VPN und Security-Dashboard
