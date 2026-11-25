"""Nomi dei tasti che tiny-dfr accetta in Action (enum Key di input-linux 0.7.1, la versione nel Cargo.lock di tiny-dfr
a79f2f4). Generato dal sorgente del crate: un nome che non è qui fa scartare a tiny-dfr l'intero config.toml."""
KEYS = frozenset("""
Esc Num1 Num2 Num3 Num4 Num5 Num6 Num7 Num8 Num9 Num0 Minus Equal Backspace Tab Q W E R T Y U I O P LeftBrace
RightBrace Enter LeftCtrl A S D F G H J K L Semicolon Apostrophe Grave LeftShift Backslash Z X C V B N M Comma Dot
Slash RightShift KpAsterisk LeftAlt Space CapsLock F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 NumLock ScrollLock Kp7 Kp8 Kp9
KpMinus Kp4 Kp5 Kp6 KpPlus Kp1 Kp2 Kp3 Kp0 KpDot ZenkakuHankaku NonUsBackslashAndPipe F11 F12 Ro Katakana Hiragana
Henkan KatakanaHiragana Muhenkan KpJpComma KpEnter RightCtrl KpSlash Sysrq RightAlt LineFeed Home Up PageUp Left
Right End Down PageDown Insert Delete Macro Mute VolumeDown VolumeUp Power KpEqual KpPlusMinus Pause Scale KpComma
Hangul Hanja Yen LeftMeta RightMeta Compose Stop Again Props Undo Front Copy Open Paste Find Cut Help Menu Calc
Setup Sleep Wakeup File SendFile DeleteFile Xfer Prog1 Prog2 WWW MSDOS Coffee RotateDisplay CycleWindows Mail
Bookmarks Computer Back Forward CloseCD EjectCD EjectCloseCD NextSong PlayPause PreviousSong StopCD Record Rewind
Phone Iso Config Homepage Refresh Exit Move Edit ScrollUp ScrollDown KpLeftParen KpRightParen New Redo F13 F14 F15
F16 F17 F18 F19 F20 F21 F22 F23 F24 PlayCD PauseCD Prog3 Prog4 AllApplications Suspend Close Play FastForward
BassBoost Print Hp Camera Sound Question Email Chat Search Connect Finance Sport Shop Alterase Cancel BrightnessDown
BrightnessUp Media SwitchVideoMode IllumToggle IllumDown IllumUp Send Reply ForwardMail Save Documents Battery
Bluetooth WLAN UWB Unknown VideoNext VideoPrev BrightnessCycle BrightnessAuto DisplayOff WWAN Rfkill MicMute
ReservedFF Button0 Button1 Button2 Button3 Button4 Button5 Button6 Button7 Button8 Button9 ButtonLeft ButtonRight
ButtonMiddle ButtonSide ButtonExtra ButtonForward ButtonBack ButtonTask ButtonTrigger ButtonThumb ButtonThumb2
ButtonTop ButtonTop2 ButtonPinkie ButtonBase ButtonBase2 ButtonBase3 ButtonBase4 ButtonBase5 ButtonBase6 ButtonDead
ButtonSouth ButtonEast ButtonC ButtonNorth ButtonWest ButtonZ ButtonTL ButtonTR ButtonTL2 ButtonTR2 ButtonSelect
ButtonStart ButtonMode ButtonThumbl ButtonThumbr ButtonToolPen ButtonToolRubber ButtonToolBrush ButtonToolPencil
ButtonToolAirbrush ButtonToolFinger ButtonToolMouse ButtonToolLens ButtonToolQuintTap ButtonStylus3 ButtonTouch
ButtonStylus ButtonStylus2 ButtonToolDoubleTap ButtonToolTripleTap ButtonToolQuadtap ButtonWheel ButtonGearUp Ok
Select Goto Clear Power2 Option Info Time Vendor Archive Program Channel Favorites EPG PVR MHP Language Title
Subtitle Angle FullScreen Mode Keyboard AspectRatio PC TV TV2 VCR VCR2 Sat Sat2 CD Tape Radio Tuner Player Text Dvd
Aux Mp3 Audio Video Directory List Memo Calendar Red Green Yellow Blue ChannelUp ChannelDown First Last Ab Next
Restart Slow Shuffle Break Previous Digits Teen Twen Videophone Games ZoomIn ZoomOut ZoomReset WordProcessor Editor
Spreadsheet GraphicsEditor Presentation Database News Voicemail AddressBook Messenger DisplayToggle SpellCheck
Logoff Dollar Euro FrameBack FrameForward ContextMenu MediaRepeat TenChannelsUp TenChannelsDown Images DelEol DelEos
InsLine DelLine Fn FnEsc FnF1 FnF2 FnF3 FnF4 FnF5 FnF6 FnF7 FnF8 FnF9 FnF10 FnF11 FnF12 Fn1 Fn2 FnD FnE FnF FnS FnB
BrlDot1 BrlDot2 BrlDot3 BrlDot4 BrlDot5 BrlDot6 BrlDot7 BrlDot8 BrlDot9 BrlDot10 Numeric0 Numeric1 Numeric2 Numeric3
Numeric4 Numeric5 Numeric6 Numeric7 Numeric8 Numeric9 NumericStar NumericPound NumericA NumericB NumericC NumericD
CameraFocus WpsButton TouchpadToggle TouchpadOn TouchpadOff CameraZoomin CameraZoomout CameraUp CameraDown
CameraLeft CameraRight AttendantOn AttendantOff AttendantToggle LightsToggle ButtonDpadUp ButtonDpadDown
ButtonDpadLeft ButtonDpadRight AlsToggle RotateLockToggle RefreshRateToggle ButtonConfig TaskManager Journal
ControlPanel AppSelect Screensaver Voicecommand Assistant KbdLayoutNext EmojiPicker Dictate CameraAccessEnable
CameraAccessDisable CameraAccessToggle Accessibility DoNotDisturb BrightnessMin BrightnessMax InputAssistPrev
InputAssistNext InputAssistPrevGroup InputAssistNextGroup InputAssistAccept InputAssistCancel RightUp RightDown
LeftUp LeftDown RootMenu MediaTopMenu Numeric11 Numeric12 AudioDesc Audio3dMode NextFavorite StopRecord PauseRecord
Vod Unmute FastReverse SlowReverse Data OnscreenKeyboard PrivacyScreenToggle SelectiveScreenshot NextElement
PreviousElement AutopilotEngageToggle MarkWaypoint SOS NavChart FishingChart SingleRangeRadar DualRangeRadar
RadarOverlay TraditionalSonar ClearVuSonar SideVuSonar NavInfo BrightnessMenu Macro1 Macro2 Macro3 Macro4 Macro5
Macro6 Macro7 Macro8 Macro9 Macro10 Macro11 Macro12 Macro13 Macro14 Macro15 Macro16 Macro17 Macro18 Macro19 Macro20
Macro21 Macro22 Macro23 Macro24 Macro25 Macro26 Macro27 Macro28 Macro29 Macro30 MacroRecordStart MacroRecordStop
MacroPresetCycle MacroPreset1 MacroPreset2 MacroPreset3 KbdLcdMenu1 KbdLcdMenu2 KbdLcdMenu3 KbdLcdMenu4 KbdLcdMenu5
ButtonTriggerHappy1 ButtonTriggerHappy2 ButtonTriggerHappy3 ButtonTriggerHappy4 ButtonTriggerHappy5
ButtonTriggerHappy6 ButtonTriggerHappy7 ButtonTriggerHappy8 ButtonTriggerHappy9 ButtonTriggerHappy10
ButtonTriggerHappy11 ButtonTriggerHappy12 ButtonTriggerHappy13 ButtonTriggerHappy14 ButtonTriggerHappy15
ButtonTriggerHappy16 ButtonTriggerHappy17 ButtonTriggerHappy18 ButtonTriggerHappy19 ButtonTriggerHappy20
ButtonTriggerHappy21 ButtonTriggerHappy22 ButtonTriggerHappy23 ButtonTriggerHappy24 ButtonTriggerHappy25
ButtonTriggerHappy26 ButtonTriggerHappy27 ButtonTriggerHappy28 ButtonTriggerHappy29 ButtonTriggerHappy30
ButtonTriggerHappy31 ButtonTriggerHappy32 ButtonTriggerHappy33 ButtonTriggerHappy34 ButtonTriggerHappy35
ButtonTriggerHappy36 ButtonTriggerHappy37 ButtonTriggerHappy38 ButtonTriggerHappy39 ButtonTriggerHappy40
""".split())
