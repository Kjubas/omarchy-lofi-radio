import QtQuick
import Quickshell.Io

Rectangle {
    id: root
    implicitWidth: showVol ? 38 : 28
    implicitHeight: 24
    radius: 8

    property bool isPlaying: false
    property real volume: 0.8
    property bool showVol: false
    property var moods: [
        { id: "chill", icon: "♫", color: "#a6e3a1" },
        { id: "rainy", icon: "☂", color: "#89b4fa" },
        { id: "study", icon: "☕", color: "#f9e2af" }
    ]
    property int moodIndex: 0

    color: root.isPlaying ? Qt.rgba(166/255, 227/255, 161/255, 0.16) : "transparent"
    border.width: root.isPlaying ? 1 : 0
    border.color: root.moods[root.moodIndex].color

    Behavior on color { ColorAnimation { duration: 200 } }
    Behavior on implicitWidth { NumberAnimation { duration: 120 } }

    Component.onDestruction: {
        stopProc.running = false;
        stopProc.running = true;
    }

    Timer {
        id: hideVolTimer
        interval: 1200
        onTriggered: root.showVol = false
    }

    Process {
        id: volProc
        command: ["bash", "-c", "echo '" + root.volume.toFixed(2) + "' > /tmp/omarchy-lofi.vol"]
    }

    Process {
        id: startProc
        command: [
            "bash", "-c",
            "[ -f /tmp/omarchy-lofi.pid ] && kill -9 $(cat /tmp/omarchy-lofi.pid) 2>/dev/null; echo '" +
            root.volume.toFixed(2) + "' > /tmp/omarchy-lofi.vol; exec python3 '" +
            Qt.resolvedUrl("lofi.py").toString().replace("file://", "") + "' '" +
            root.moods[root.moodIndex].id + "'"
        ]
    }

    Process {
        id: stopProc
        command: [
            "bash", "-c",
            "[ -f /tmp/omarchy-lofi.pid ] && kill -9 $(cat /tmp/omarchy-lofi.pid) 2>/dev/null; rm -f /tmp/omarchy-lofi.pid"
        ]
    }

    Text {
        id: moodIcon
        anchors.centerIn: parent
        text: root.showVol ? Math.round(root.volume * 100) + "%" : root.moods[root.moodIndex].icon
        color: root.isPlaying ? root.moods[root.moodIndex].color : "#cdd6f4"
        font.pixelSize: root.showVol ? 11 : 15
        font.bold: root.showVol
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        hoverEnabled: true

        onEntered: if (!root.isPlaying) root.color = Qt.rgba(255, 255, 255, 0.08)
        onExited: if (!root.isPlaying) root.color = "transparent"

        onWheel: (wheel) => {
            let delta = wheel.angleDelta.y > 0 ? 0.05 : -0.05;
            root.volume = Math.max(0.0, Math.min(1.5, root.volume + delta));
            root.showVol = true;
            hideVolTimer.restart();
            volProc.running = false;
            volProc.running = true;
        }

        onClicked: (mouse) => {
            if (mouse.button === Qt.LeftButton) {
                root.isPlaying = !root.isPlaying;
                if (root.isPlaying) {
                    startProc.running = false;
                    startProc.running = true;
                } else {
                    startProc.running = false;
                    stopProc.running = false;
                    stopProc.running = true;
                }
            } else if (mouse.button === Qt.RightButton) {
                root.moodIndex = (root.moodIndex + 1) % root.moods.length;
                if (root.isPlaying) {
                    startProc.running = false;
                    startProc.running = true;
                }
            }
        }
    }
}
