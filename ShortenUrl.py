import os
import sys
import win32api         # package pywin32
import win32con
import win32gui_struct
import time
import pyperclip
import webbrowser

from win10toast import ToastNotifier
try:
    import winxpgui as win32gui
except ImportError:
    import win32gui


class SysTrayIcon(object):

    QUIT = 'QUIT'
    SPECIAL_ACTIONS = [QUIT]

    FIRST_ID = 1023

    def __init__(self,
                 icon,
                 hover_text,
                 menu_options,
                 on_quit=None,
                 default_menu_index=None,
                 window_class_name=None,):

        self.icon = icon
        self.hover_text = hover_text
        self.on_quit = on_quit

        menu_options = menu_options + (('Quit', None, self.QUIT),)
        self._next_action_id = self.FIRST_ID
        self.menu_actions_by_id = set()
        self.menu_options = self._add_ids_to_menu_options(list(menu_options))
        self.menu_actions_by_id = dict(self.menu_actions_by_id)
        del self._next_action_id

        self.default_menu_index = (default_menu_index or 0)
        self.window_class_name = window_class_name or "SysTrayIconPy"

        message_map = {win32gui.RegisterWindowMessage("TaskbarCreated"): self.restart,
                       win32con.WM_DESTROY: self.destroy,
                       win32con.WM_COMMAND: self.command,
                       win32con.WM_USER + 20: self.notify, }
        # Register the Window class.
        window_class = win32gui.WNDCLASS()
        hinst = window_class.hInstance = win32gui.GetModuleHandle(None)
        window_class.lpszClassName = self.window_class_name
        window_class.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
        window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground = win32con.COLOR_WINDOW
        window_class.lpfnWndProc = message_map  # could also specify a wndproc.
        classAtom = win32gui.RegisterClass(window_class)
        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(classAtom,
                                          self.window_class_name,
                                          style,
                                          0,
                                          0,
                                          win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT,
                                          0,
                                          0,
                                          hinst,
                                          None)
        win32gui.UpdateWindow(self.hwnd)
        self.notify_id = None
        self.refresh_icon()

        win32gui.PumpMessages()

    def _add_ids_to_menu_options(self, menu_options):
        result = []
        for menu_option in menu_options:
            option_text, option_icon, option_action = menu_option
            if callable(option_action) or option_action in self.SPECIAL_ACTIONS:
                self.menu_actions_by_id.add(
                    (self._next_action_id, option_action))
                result.append(menu_option + (self._next_action_id,))
            elif non_string_iterable(option_action):
                result.append((option_text,
                               option_icon,
                               self._add_ids_to_menu_options(option_action),
                               self._next_action_id))
            else:
                print('Unknown item', option_text, option_icon, option_action)
            self._next_action_id += 1
        return result

    def refresh_icon(self):
        # Try and find a custom icon
        hinst = win32gui.GetModuleHandle(None)
        if os.path.isfile(self.icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(hinst,
                                       self.icon,
                                       win32con.IMAGE_ICON,
                                       0,
                                       0,
                                       icon_flags)
        else:
            print("Can't find icon file - using default.")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        if self.notify_id:
            message = win32gui.NIM_MODIFY
        else:
            message = win32gui.NIM_ADD
        self.notify_id = (self.hwnd,
                          0,
                          win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                          win32con.WM_USER + 20,
                          hicon,
                          self.hover_text)
        win32gui.Shell_NotifyIcon(message, self.notify_id)

    def restart(self, hwnd, msg, wparam, lparam):
        self.refresh_icon()

    def destroy(self, hwnd, msg, wparam, lparam):
        if self.on_quit:
            self.on_quit(self)
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0)  # Terminate the app.

    def notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONDBLCLK:
            self.execute_menu_option(self.default_menu_index + self.FIRST_ID)
        elif lparam == win32con.WM_RBUTTONUP:
            self.show_menu()
        elif lparam == win32con.WM_LBUTTONUP:
            pass
        return True

    def show_menu(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu, self.menu_options)
        #win32gui.SetMenuDefaultItem(menu, 1000, 0)

        pos = win32gui.GetCursorPos()
        # See
        # http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu,
                                win32con.TPM_LEFTALIGN,
                                pos[0],
                                pos[1],
                                0,
                                self.hwnd,
                                None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def create_menu(self, menu, menu_options):
        for option_text, option_icon, option_action, option_id in menu_options[::-1]:
            if option_icon:
                option_icon = self.prep_menu_icon(option_icon)

            if option_id in self.menu_actions_by_id:
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                hbmpItem=option_icon,
                                                                wID=option_id)
                win32gui.InsertMenuItem(menu, 0, 1, item)
            else:
                submenu = win32gui.CreatePopupMenu()
                self.create_menu(submenu, option_action)
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                hbmpItem=option_icon,
                                                                hSubMenu=submenu)
                win32gui.InsertMenuItem(menu, 0, 1, item)

    def prep_menu_icon(self, icon):
        # First load the icon.
        ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
        ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
        hicon = win32gui.LoadImage(
            0, icon, win32con.IMAGE_ICON, ico_x, ico_y, win32con.LR_LOADFROMFILE)

        hdcBitmap = win32gui.CreateCompatibleDC(0)
        hdcScreen = win32gui.GetDC(0)
        hbm = win32gui.CreateCompatibleBitmap(hdcScreen, ico_x, ico_y)
        hbmOld = win32gui.SelectObject(hdcBitmap, hbm)
        # Fill the background.
        brush = win32gui.GetSysColorBrush(win32con.COLOR_MENU)
        win32gui.FillRect(hdcBitmap, (0, 0, 16, 16), brush)
        # unclear if brush needs to be feed.  Best clue I can find is:
        # "GetSysColorBrush returns a cached brush instead of allocating a new
        # one." - implies no DeleteObject
        # draw the icon
        win32gui.DrawIconEx(hdcBitmap, 0, 0, hicon, ico_x,
                            ico_y, 0, 0, win32con.DI_NORMAL)
        win32gui.SelectObject(hdcBitmap, hbmOld)
        win32gui.DeleteDC(hdcBitmap)

        return hbm

    def command(self, hwnd, msg, wparam, lparam):
        id = win32gui.LOWORD(wparam)
        self.execute_menu_option(id)

    def execute_menu_option(self, id):
        menu_action = self.menu_actions_by_id[id]
        if menu_action == self.QUIT:
            win32gui.DestroyWindow(self.hwnd)
        else:
            menu_action(self)


def non_string_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return not isinstance(obj, str)

# Minimal self test. You'll need a bunch of ICO files in the current working
# directory in order for this to work...

# Xử lý clipboard và link url

sys.path.append(os.path.abspath("SO_site-packages"))

# kiểm tra xem có đúng định dạng url


def isUrl(text):
    normal_url = 'https://'
    normal_url_2 = 'http://'
    bitly_url = 'http://bit.ly/'
    if (text.startswith(bitly_url)):
        return 2
    if (text.startswith(normal_url)):
        return 1
    if (text.startswith(normal_url_2)):
        return 1
    return 0

tmp_value = ""
recent_value = ""
isNotify = True
isAuto = True


def auto_shorten_url():
    while True:
        global recent_value, tmp_value
        recent_value = tmp_value
        tmp_value = pyperclip.paste()
        if ((tmp_value != recent_value) and (isAuto is True)):
            if isUrl(tmp_value) == 1:
                recent_value = tmp_value
                response = bitly.shorten(uri=recent_value)
                shorturl = response['url']
                pyperclip.copy(shorturl)
                # print(shorturl)
                # print("Value changed: %s" % str(recent_value)[:20])
        time.sleep(0.1)

# Chương trình ở dưới thanh taskbar
if __name__ == '__main__':
    import itertools
    import glob
    import bitly_api
    import _thread

    _thread.start_new_thread(auto_shorten_url, ())

    bitly = bitly_api.Connection(
        access_token='c42af425764e7f7623178e3ebee02965b0ef0688')

    icons = itertools.cycle(glob.glob('*.ico'))
    hover_text = "ShortenURL - TX"

    toaster = ToastNotifier()

    def shorten(sysTrayIcon):
        value = pyperclip.paste()
        longurl = str(value)
        if (isUrl(longurl) == 1):
            response = bitly.shorten(uri=longurl)
            shorturl = response['url']
            pyperclip.copy(shorturl)
            # print(shorturl)
            if (isNotify is True):
                toaster.show_toast("Thông báo", 'Đã rút gọn link', icon_path='url.ico',
                                   duration=1.5, threaded=True)

        else:
            if (isNotify is True):
                toaster.show_toast("Thông báo", 'Rút gọn thất bại', icon_path='url.ico',
                                   duration=1.5, threaded=True)

    def expand(sysTrayIcon):
        value = pyperclip.paste()
        shorturl = str(value)
        if (isUrl(shorturl) == 2):
            response = bitly.expand(shortUrl=shorturl)
            longurl = response[0]['long_url']
            pyperclip.copy(longurl)
            # print(longurl)
            global recent_value, tmp_value
            recent_value = pyperclip.paste()
            tmp_value = pyperclip.paste()

            if (isNotify is True):
                toaster.show_toast("Thông báo", 'Đã mở rộng link rút gọn', icon_path='url.ico',
                                   duration=1.5, threaded=True)
        else:
            if (isNotify is True):
                toaster.show_toast("Thông báo", 'Mở rộng thất bại', icon_path='url.ico',
                                   duration=1.5, threaded=True)

    def isnotify(sysTrayIcon):
        global isNotify
        isNotify = not(isNotify)
        if (isNotify is True):
            strnotify = 'Bật'
        else:
            strnotify = 'Tắt'
        message = 'Trạng thái thông báo : ' + strnotify
        toaster.show_toast("Thông báo", message, icon_path='url.ico',
                           duration=1.5, threaded=True)

    def isauto(sysTrayIcon):
        global isAuto
        isAuto = not(isAuto)
        if (isAuto is True):
            strauto = 'Bật'
        else:
            strauto = 'Tắt'
        message = 'Auto rút gọn : ' + strauto
        toaster.show_toast("Thông báo", message, icon_path='url.ico',
                           duration=1.5, threaded=True)

    def sharefb(sysTrayIcon):
        urlsharefb = 'https://www.facebook.com/sharer/sharer.php?u='
        url = urlsharefb + pyperclip.paste()
        webbrowser.open_new_tab(url)

    menu_options = (('Rút gọn', None, shorten),
                    ('Mở rộng', None, expand),
                    ('Chia sẻ Fb', None, sharefb),
                    ('Auto rút gọn', None, isauto),
                    ('Thông báo', None, isnotify)
                    )

    SysTrayIcon(next(icons), hover_text, menu_options,
                on_quit=None, default_menu_index=1)
