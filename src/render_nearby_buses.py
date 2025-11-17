import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='pygame.pkgdata')

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import time
import threading
import tkinter as tk
import random
import pygame
from PIL import Image, ImageTk, ImageDraw, ImageFont
from src.track_nearby_buses import track_nearby_buses


pygame.mixer.init()


bus_route_colors = {
    'small': [
        '68'
    ],
    'grey': [
        '33', '49', '4', '14', '84'
    ],
    'blue': [
        '25', '44', '99'
    ],
    'green': [
        'R4'
    ]
}

bus_sign_offsets = {
    'small': (54, 20),
    'grey': (154, 20),
    'blue': (154, 28),
    'green': (154, 28)
}


class RenderState:

    class RenderedBus:

        def __init__(self, parent, bus_data):
            self.parent = parent
            self.bus_data = bus_data
            color_list = [color for color in bus_route_colors if bus_data['route_name'] in bus_route_colors[color]]
            self.bus_color = 'grey' if len(color_list) == 0 else color_list[0]
            self.bus_img_up = parent.bus_images[self.bus_color]['up']
            self.bus_img_down = parent.bus_images[self.bus_color]['down']
            self.x = -self.bus_img_up.width()
            self.y = self.parent.canvas_shape[1] - self.bus_img_up.height()
            self.text_img = create_text_image(
                text=bus_data['route_name'],
                font_path="assets/fonts/vhs-gothic.ttf",
                font_size=10,
                color=(255, 165, 0, 255)  # orange
            )
            self.active = True

        def update(self, dt_s: float):
            self.x += 200 * dt_s
            if self.x > self.parent.canvas_shape[0]:
                self.active = False

        def render(self):
            if not self.active:
                return False
            is_up = self.x % 80 < 40
            self.parent.canvas.create_image(self.x, self.y, anchor="nw", image=self.bus_img_up if is_up else self.bus_img_down)
            self.parent.canvas.create_image(self.x + bus_sign_offsets[self.bus_color][0], self.y + bus_sign_offsets[self.bus_color][1] - (4 if is_up else 0), anchor="nw", image=self.text_img)
            return True

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.canvas_shape = (canvas.winfo_screenwidth(), canvas.winfo_screenheight())
        self.bus_images = {
            'small': {
                'up': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_small_up.png'))),
                'down': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_small_down.png')))
            },
            'grey': {
                'up': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_grey_up.png'))),
                'down': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_grey_down.png')))
            },
            'blue': {
                'up': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_blue_up.png'))),
                'down': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_blue_down.png')))
            },
            'green': {
                'up': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_green_up.png'))),
                'down': ImageTk.PhotoImage(Image.open(os.path.join('assets', 'images', 'bus_green_down.png')))
            }
        }

        self.buses = []
        self.bus_lock = threading.RLock()
        self.bus_index = 0
        self.bus_interval = lambda: random.uniform(1.5, 2.5)
        self.bus_interval_timer = 0

        self.rendered_buses = []
        self.previous_advance_time = None

        self.engine_sound = pygame.mixer.Sound(os.path.join('assets', 'sounds', 'engine.wav'))
        self.engine_channel = self.engine_sound.play(loops=-1)
        self.engine_channel.set_volume(0)

    def advance(self):
        if self.previous_advance_time is None:
            self.previous_advance_time = time.perf_counter()
            return
        current_time = time.perf_counter()
        dt_s = current_time - self.previous_advance_time

        self.bus_interval_timer = max(0, self.bus_interval_timer - dt_s)
        if self.bus_interval_timer == 0:
            with self.bus_lock:
                if len(self.buses) > self.bus_index:
                    print(f'{self.buses[self.bus_index]['timestamp']}: Observed {self.buses[self.bus_index]['route_name']} - {self.buses[self.bus_index]['trip_id']} - {self.buses[self.bus_index]['trip_name']}, Scheduled at {self.buses[self.bus_index]['departure_time']}')
                    self.rendered_buses.append(self.RenderedBus(self, self.buses[self.bus_index]))
                    self.bus_index += 1
                    self.bus_interval_timer = self.bus_interval()
                else:
                    self.bus_interval_timer = 0.5
        
        for bus in self.rendered_buses:
            bus.update(dt_s)
        
        self.previous_advance_time = current_time

    def render(self):
        self.canvas.delete('all')
        any_rendered = False
        for bus in self.rendered_buses:
            if bus.render():
                any_rendered = True
        if any_rendered:
            self.engine_channel.set_volume(min(0.25, self.engine_channel.get_volume() + 0.01))
        else:
            self.engine_channel.set_volume(max(0, self.engine_channel.get_volume() - 0.0005))

def create_text_image(text: str, font_path: str, font_size: int, color: tuple):
    font = ImageFont.truetype(font_path, font_size)
    img = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), text, font=font, fill=color)

    return ImageTk.PhotoImage(img)


def update(root: tk.Tk, canvas: tk.Canvas, state: RenderState):
    state.advance()
    state.render()
    root.after(10, update, root, canvas, state)


def beep():
    sound = pygame.mixer.Sound(os.path.join('assets', 'sounds', 'beep3.wav'))
    sound.set_volume(0.5)
    sound.play()


if __name__ == '__main__':
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.attributes('-transparentcolor', 'white')
    root.overrideredirect(True)
    root.bind('<Escape>', lambda e: root.destroy())
    root.bind('<Button-1>', lambda e: beep())

    canvas = tk.Canvas(root, width=root.winfo_screenwidth(), height=root.winfo_screenheight(), bg='white', highlightthickness=0)
    canvas.pack()

    state = RenderState(canvas)

    tracking_thread = threading.Thread(target=track_nearby_buses, args=(state.buses, state.bus_lock), daemon=True)
    tracking_thread.start()

    update(root, canvas, state)

    root.mainloop()