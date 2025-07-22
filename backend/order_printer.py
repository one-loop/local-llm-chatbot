import time
import os
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

ORDERS_PATH = os.path.abspath("orders.txt")

class OrderPrinterHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == ORDERS_PATH:
            print("[Watcher] Detected new order. Sending to printer...")
            self.print_file()

    def print_file(self):
        try:
            # For Linux/macOS
            os.system(f"lp {ORDERS_PATH}")
            
            # For Windows, use this instead:
            # subprocess.run(['notepad.exe', '/p', ORDERS_PATH], shell=True)
        except Exception as e:
            print(f"[Printer Error] {e}")

if __name__ == "__main__":
    event_handler = OrderPrinterHandler()
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(ORDERS_PATH) or ".", recursive=False)
    
    print(f"[Watcher] Monitoring {ORDERS_PATH} for changes...")
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
