import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// MacBook Manager nella barra di Omarchy (MacBookPro14,3). Legge `macbook-manager bar` (JSON compatto, ~0,1 s) ogni
// 30 s e `macbook-manager status --json` (lento, ~2 s) ogni 5 minuti e all'apertura, per batteria, registratore della
// batteria (il timer utente macbook-manager-battery-log.timer, che gira sempre, anche senza la barra), ultima sessione a
// batteria, avvisi e impostazioni di avvio. I pulsanti aprono MacBook Manager sulla scheda giusta. Tutto il testo che
// arriva dai comandi passa da PlainText (niente markup).
Panel {
  id: root
  moduleName: "macbookpro14-3.manager"
  ipcTarget: "macbookpro14-3.manager"

  readonly property bool showBattery: setting("showBattery", false) === true
  property var info: ({})
  property var warnings: []
  property bool warningsLoaded: false

  readonly property var bat: info.battery || ({})
  readonly property int pct: bat.pct !== undefined ? Math.round(bat.pct) : -1
  readonly property string stateText: {
    var k = "state." + String(bat.status || "unknown")
    var t = strings.t(k)
    return t === k ? strings.t("state.unknown") : t
  }

  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  function duration(minutes) {
    var m = Math.max(0, Math.round(minutes))
    return m < 60 ? strings.t("minutes").arg(m) : strings.t("hoursMinutes").arg(Math.floor(m / 60)).arg(m % 60)
  }
  function age(seconds) {
    return seconds < 120 ? strings.t("seconds").arg(seconds) : duration(seconds / 60)
  }
  function num(v, d) { return Commons.I18n.formatNumber(Number(v || 0), d) }
  function gpuName(g) { return g === "intel" ? strings.t("gpu.intel") : g === "radeon" ? strings.t("gpu.radeon") : "?" }

  // Testo di un comando: solo JSON, con limiti di dimensione; tutto il resto viene ignorato.
  function parse(text, fallback) {
    if (!text || text.length > 200000) return fallback
    try { return JSON.parse(text) } catch (e) { return fallback }
  }

  function refresh() { if (!barProc.running) barProc.running = true }
  function refreshStatus() { if (!statusProc.running) statusProc.running = true }
  function openManager(tab) {
    Quickshell.execDetached(tab ? ["macbook-manager", "gui", "--tab", tab] : ["macbook-manager", "gui"])
    root.close()
  }

  Process {
    id: barProc
    command: ["macbook-manager", "bar"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.info = root.parse(text, root.info) }
  }

  Process {
    id: statusProc
    command: ["macbook-manager", "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var items = root.parse(text, null)
        if (!Array.isArray(items)) return
        var out = []
        for (var i = 0; i < items.length && out.length < 8; i++) {
          var it = items[i]
          if (it && (it.level === "warn" || it.level === "err"))
            out.push({ level: String(it.level), text: String(it.group || "").slice(0, 40) + " · " + String(it.label || "").slice(0, 60)
                       + ": " + String(it.value || "").slice(0, 120) })
        }
        root.warnings = out
        root.warningsLoaded = true
      }
    }
  }

  Process {
    id: loggerProc
    command: ["systemctl", "--user", "enable", "--now", "macbook-manager-battery-log.timer"]
    onExited: root.refresh()
  }

  // "Servizio": gira finché c'è la barra (il registratore vero è il timer di systemd, che non dipende dalla barra).
  Timer { interval: 30000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refresh() }
  Timer { interval: 300000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.refreshStatus() }
  onOpenedChanged: if (opened) { refresh(); refreshStatus() }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // ---------- barra ----------
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰌢"   // nf-md-laptop
    labelText: root.showBattery && !vertical && root.pct >= 0 ? Commons.I18n.formatNumber(root.pct) + "%" : ""
    slotSize: Style.bar.iconSlot * (labelText !== "" ? 2 : 1)
    foreground: root.warnings.length > 0 ? Commons.Color.urgent : root.barForeground
    tooltipText: root.warnings.length > 0
      ? strings.tn("tooltip.warnings", root.warnings.length).arg(root.pct >= 0 ? root.pct + "%" : "-").arg(root.warnings.length)
      : strings.t("tooltip").arg(root.pct >= 0 ? root.pct + "% · " + root.stateText : "-")
    onPressed: function(b) { root.toggle() }
  }

  // ---------- pannello ----------
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: panel.loadedContent
    contentWidth: panel.fittedContentWidth(Style.space(420))
    contentHeight: panel.fittedContentHeight(panel.loadedContentHeight)

    content: PanelKeyCatcher {
      anchors.fill: parent
      implicitHeight: column.implicitHeight
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        width: parent.width
        spacing: Style.space(12)

        // Intestazione: batteria adesso
        Row {
          width: parent.width
          spacing: Style.space(14)
          PlainText { text: "󰌢"; font.pixelSize: Style.font.display; anchors.verticalCenter: parent.verticalCenter }
          Column {
            width: parent.width - Style.space(60)
            spacing: Style.space(2)
            PlainText { text: strings.t("title"); font.pixelSize: Style.font.title; font.bold: true }
            PlainText {
              width: parent.width
              wrapMode: Text.Wrap
              text: root.pct < 0 ? "-" : strings.t("battery.line").arg(root.pct).arg(root.stateText).arg(root.num(Math.abs(root.bat.power_w || 0), 1))
                + (root.bat.time_to_empty > 0 && !root.bat.ac ? " · " + strings.t("battery.toEmpty").arg(root.duration(root.bat.time_to_empty / 60)) : "")
                + (root.bat.time_to_full > 0 && root.bat.ac ? " · " + strings.t("battery.toFull").arg(root.duration(root.bat.time_to_full / 60)) : "")
            }
            PlainText {
              opacity: 0.7
              text: root.bat.health ? strings.t("battery.detail").arg(root.num(root.bat.health, 0)).arg(root.num(root.bat.cycles, 0)).arg(root.num(root.bat.temp, 1)) : ""
            }
          }
        }

        PanelSeparator { width: parent.width }

        // Registratore della batteria
        PanelSectionHeader { text: strings.t("logger.header"); foreground: root.barForeground }
        Row {
          width: parent.width
          spacing: Style.space(10)
          readonly property var lg: root.info.logger || ({})
          PlainText {
            width: parent.width - (startButton.visible ? startButton.width + Style.space(10) : 0)
            wrapMode: Text.Wrap
            anchors.verticalCenter: parent.verticalCenter
            color: parent.lg.active === false ? Commons.Color.urgent : root.barForeground
            text: parent.lg.active ? strings.t("logger.active").arg(parent.lg.age_s !== null && parent.lg.age_s !== undefined ? root.age(parent.lg.age_s) : "-").arg(root.num(parent.lg.samples, 0))
                : parent.lg.active === false ? strings.t("logger.stopped") : "-"
          }
          Button {
            id: startButton
            visible: parent.lg.active === false
            text: strings.t("logger.start")
            onClicked: loggerProc.running = true
          }
        }

        // Ultima sessione a batteria
        PanelSectionHeader { text: strings.t("session.header"); foreground: root.barForeground }
        PlainText {
          width: parent.width
          wrapMode: Text.Wrap
          readonly property var s: root.info.last_session || null
          text: !s ? strings.t("session.none")
            : strings.t("session.line").arg(root.duration(s.duration_min)).arg(root.num(s.start_pct, 0)).arg(root.num(s.end_pct, 0))
                .arg(root.num(s.avg_w, 1)).arg(root.num(s.projected_h, 1))
        }

        // Avvisi (da status --json)
        PanelSectionHeader { text: strings.t("warnings.header"); foreground: root.barForeground }
        PlainText {
          visible: !root.warningsLoaded || root.warnings.length === 0
          text: root.warningsLoaded ? strings.t("warnings.none") : strings.t("warnings.loading")
          opacity: 0.8
        }
        Repeater {
          model: root.warnings
          PlainText {
            required property var modelData
            width: column.width
            wrapMode: Text.Wrap
            color: modelData.level === "err" ? Commons.Color.urgent : root.barForeground
            text: "• " + modelData.text
          }
        }

        // Schermo e avvio (NVRAM)
        PanelSectionHeader { text: strings.t("boot.header"); foreground: root.barForeground }
        PlainText {
          width: parent.width
          wrapMode: Text.Wrap
          readonly property var d: root.info.display || ({})
          readonly property var n: root.info.nvram || ({})
          text: strings.t("boot.line").arg(root.gpuName(d.now)).arg(root.gpuName(d.next))
            .arg(n.chime === false ? strings.t("chime.off") : strings.t("chime.on"))
            .arg(n.opencore_booted ? strings.t("yes") : strings.t("no"))
        }

        PanelSeparator { width: parent.width }

        // Scorciatoie nel manager
        Flow {
          width: parent.width
          spacing: Style.space(8)
          Button { text: strings.t("open.manager"); iconText: "󰌢"; onClicked: root.openManager("") }
          Button { text: strings.t("open.battery"); onClicked: root.openManager("batteria") }
          Button { text: strings.t("open.nvram"); onClicked: root.openManager("nvram") }
          Button { text: strings.t("open.touchbar"); onClicked: root.openManager("touchbar") }
        }
      }
    }
  }

  component PlainText: Text {
    textFormat: Text.PlainText
    color: root.barForeground
    font.family: root.bar ? root.bar.fontFamily : Style.font.family
  }
}
