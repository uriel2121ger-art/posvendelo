//go:build windows

package main

import (
	"sync"
	"syscall"
	"unsafe"
)

// Win32 window style constants.
const (
	wsOverlapped     = 0x00000000
	wsCaption        = 0x00C00000
	wsSysMenu        = 0x00080000
	wsMinimizeBox    = 0x00020000
	wsChild   = 0x40000000
	wsVisible = 0x10000000

	wsOverlappedWindow = wsOverlapped | wsCaption | wsSysMenu | wsMinimizeBox
	wsChildVisible     = wsChild | wsVisible

	ssCenter = 0x00000001

	swShow = 5

	wmDestroy = 0x0002
	wmClose   = 0x0010
	wmUser    = 0x0400

	// Custom messages for cross-goroutine UI updates.
	wmAppStatus   = wmUser + 1
	wmAppProgress = wmUser + 2
	wmAppDone     = wmUser + 3

	pbmSetRange32 = 0x0406
	pbmSetPos     = 0x0402

	colorBtnFace = 15
)

// hwnd is a Win32 window handle.
type hwnd uintptr

// wndClassEx mirrors WNDCLASSEXW.
type wndClassEx struct {
	cbSize        uint32
	style         uint32
	lpfnWndProc   uintptr
	cbClsExtra    int32
	cbWndExtra    int32
	hInstance     uintptr
	hIcon         uintptr
	hCursor       uintptr
	hbrBackground uintptr
	lpszMenuName  *uint16
	lpszClassName *uint16
	hIconSm       uintptr
}

// winMsg mirrors MSG.
type winMsg struct {
	hwnd    hwnd
	message uint32
	wParam  uintptr
	lParam  uintptr
	time    uint32
	ptX     int32
	ptY     int32
}

var (
	user32   = syscall.NewLazyDLL("user32.dll")
	kernel32 = syscall.NewLazyDLL("kernel32.dll")
	comctl32 = syscall.NewLazyDLL("comctl32.dll")

	procRegisterClassExW   = user32.NewProc("RegisterClassExW")
	procCreateWindowExW    = user32.NewProc("CreateWindowExW")
	procShowWindow         = user32.NewProc("ShowWindow")
	procUpdateWindow       = user32.NewProc("UpdateWindow")
	procGetMessageW        = user32.NewProc("GetMessageW")
	procTranslateMessage   = user32.NewProc("TranslateMessage")
	procDispatchMessageW   = user32.NewProc("DispatchMessageW")
	procDefWindowProcW     = user32.NewProc("DefWindowProcW")
	procPostQuitMessage    = user32.NewProc("PostQuitMessage")
	procSetWindowTextW     = user32.NewProc("SetWindowTextW")
	procSendMessageW       = user32.NewProc("SendMessageW")
	procLoadCursorW        = user32.NewProc("LoadCursorW")
	procGetSystemMetrics   = user32.NewProc("GetSystemMetrics")
	procGetSysColorBrush   = user32.NewProc("GetSysColorBrush")
	procInitCommonControls = comctl32.NewProc("InitCommonControls")
	procGetModuleHandleW   = kernel32.NewProc("GetModuleHandleW")
)

var gMainHwnd hwnd
var gStatusHwnd hwnd
var gProgressHwnd hwnd

// Thread-safe queue for status text from the goroutine.
var statusMu sync.Mutex
var statusQueue []string

var procPostMessageW = user32.NewProc("PostMessageW")

// wndProc is the Win32 window procedure callback.
func wndProc(h hwnd, msg uint32, wParam, lParam uintptr) uintptr {
	switch msg {
	case wmClose, wmDestroy:
		procPostQuitMessage.Call(0)
		return 0
	case wmAppStatus:
		// Dequeue the latest status text and apply it (runs on UI thread).
		statusMu.Lock()
		if len(statusQueue) > 0 {
			text := statusQueue[len(statusQueue)-1]
			statusQueue = statusQueue[:0]
			statusMu.Unlock()
			ptr, _ := syscall.UTF16PtrFromString(text)
			procSetWindowTextW.Call(uintptr(gStatusHwnd), uintptr(unsafe.Pointer(ptr)))
		} else {
			statusMu.Unlock()
		}
		return 0
	case wmAppProgress:
		// wParam contains the percentage.
		procSendMessageW.Call(uintptr(gProgressHwnd), pbmSetPos, wParam, 0)
		return 0
	case wmAppDone:
		procPostQuitMessage.Call(0)
		return 0
	}
	r, _, _ := procDefWindowProcW.Call(uintptr(h), uintptr(msg), wParam, lParam)
	return r
}

// windowsUI builds the Win32 window and runs the installer in a goroutine.
func windowsUI(appType string, run func(
	setStatus func(string),
	setProgress func(pct int),
) error) error {

	procInitCommonControls.Call()

	hInst, _, _ := procGetModuleHandleW.Call(0)

	className, _ := syscall.UTF16PtrFromString("PosvendeloStub")

	cursor, _, _ := procLoadCursorW.Call(0, 32512) // IDC_ARROW

	bgBrush, _, _ := procGetSysColorBrush.Call(colorBtnFace)

	cb := syscall.NewCallback(func(h, msg uintptr, wParam, lParam uintptr) uintptr {
		return wndProc(hwnd(h), uint32(msg), wParam, lParam)
	})

	wc := wndClassEx{
		style:         0x0003, // CS_HREDRAW | CS_VREDRAW
		lpfnWndProc:   cb,
		hInstance:     hInst,
		hCursor:       cursor,
		hbrBackground: bgBrush,
		lpszClassName: className,
	}
	wc.cbSize = uint32(unsafe.Sizeof(wc))
	procRegisterClassExW.Call(uintptr(unsafe.Pointer(&wc)))

	title := "PosVendelo — Instalador"
	if appType == AppOwner {
		title = "PosVendelo Owner — Instalador"
	}
	titlePtr, _ := syscall.UTF16PtrFromString(title)

	// Centre the window.
	smW, _, _ := procGetSystemMetrics.Call(0) // SM_CXSCREEN
	smH, _, _ := procGetSystemMetrics.Call(1) // SM_CYSCREEN
	winW, winH := uintptr(450), uintptr(220)
	x := (smW - winW) / 2
	y := (smH - winH) / 2

	mainWnd, _, _ := procCreateWindowExW.Call(
		0,
		uintptr(unsafe.Pointer(className)),
		uintptr(unsafe.Pointer(titlePtr)),
		wsOverlappedWindow,
		x, y, winW, winH,
		0, 0, hInst, 0,
	)
	gMainHwnd = hwnd(mainWnd)

	// Status label (STATIC).
	connecting, _ := syscall.UTF16PtrFromString("Conectando...")
	staticClass, _ := syscall.UTF16PtrFromString("STATIC")
	statusWnd, _, _ := procCreateWindowExW.Call(
		0,
		uintptr(unsafe.Pointer(staticClass)),
		uintptr(unsafe.Pointer(connecting)),
		wsChildVisible|ssCenter,
		20, 60, 410, 36,
		mainWnd, 0, hInst, 0,
	)
	gStatusHwnd = hwnd(statusWnd)

	// Progress bar.
	pbClass, _ := syscall.UTF16PtrFromString("msctls_progress32")
	pbWnd, _, _ := procCreateWindowExW.Call(
		0,
		uintptr(unsafe.Pointer(pbClass)),
		0,
		wsChildVisible,
		20, 120, 410, 26,
		mainWnd, 0, hInst, 0,
	)
	gProgressHwnd = hwnd(pbWnd)
	// Range 0-100
	procSendMessageW.Call(uintptr(gProgressHwnd), pbmSetRange32, 0, 100)

	procShowWindow.Call(mainWnd, swShow)
	procUpdateWindow.Call(mainWnd)

	// setStatus enqueues text and wakes the UI thread via PostMessage (thread-safe).
	setStatus := func(text string) {
		statusMu.Lock()
		statusQueue = append(statusQueue, text)
		statusMu.Unlock()
		procPostMessageW.Call(uintptr(gMainHwnd), wmAppStatus, 0, 0)
	}
	// setProgress posts the percentage to the UI thread (thread-safe).
	setProgress := func(pct int) {
		procPostMessageW.Call(uintptr(gMainHwnd), wmAppProgress, uintptr(pct), 0)
	}

	errCh := make(chan error, 1)
	go func() {
		errCh <- run(setStatus, setProgress)
		// Wake the message pump to process the quit.
		procPostMessageW.Call(uintptr(gMainHwnd), wmAppDone, 0, 0)
	}()

	// Message pump — blocks until WM_QUIT (sent by wmAppDone handler).
	var m winMsg
	for {
		ret, _, _ := procGetMessageW.Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if ret == 0 {
			break
		}
		procTranslateMessage.Call(uintptr(unsafe.Pointer(&m)))
		procDispatchMessageW.Call(uintptr(unsafe.Pointer(&m)))
	}

	return <-errCh
}

// showBanner is a no-op on Windows; the window is the banner.
func showBanner(appType, version string) {}

var procMessageBoxW = user32.NewProc("MessageBoxW")

// showError displays an error via MessageBox (works even after the window is destroyed).
func showError(errMsg string) {
	title, _ := syscall.UTF16PtrFromString("PosVendelo — Error")
	msg, _ := syscall.UTF16PtrFromString(errMsg)
	// MB_OK (0x00) | MB_ICONERROR (0x10)
	procMessageBoxW.Call(0, uintptr(unsafe.Pointer(msg)), uintptr(unsafe.Pointer(title)), 0x10)
}

// askInstallMode shows a Yes/No MessageBox to choose principal vs client mode.
// Uses gMainHwnd as parent so the dialog is centered on the installer window.
func askInstallMode() string {
	title, _ := syscall.UTF16PtrFromString("PosVendelo — Tipo de instalación")
	msg, _ := syscall.UTF16PtrFromString(
		"¿Esta es la PC principal del negocio?\r\n\r\n" +
			"[Sí] → PC Principal (instala servidor y base de datos)\r\n" +
			"[No] → Caja secundaria (se conecta a otro servidor en la red)")
	// MB_YESNO (0x04) | MB_ICONQUESTION (0x20)
	ret, _, _ := procMessageBoxW.Call(uintptr(gMainHwnd), uintptr(unsafe.Pointer(msg)), uintptr(unsafe.Pointer(title)), 0x24)
	// IDYES = 6, IDNO = 7
	if ret == 7 {
		return InstallClient
	}
	return InstallPrincipal
}
