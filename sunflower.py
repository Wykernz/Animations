import math
import random
import tkinter as tk

# A little sunflower, made with Python's built-in Tkinter.
W, H = 900, 700
CX, CY = W // 2, 270


def mix(a, b, t):
    """Blend two #RRGGBB colors."""
    a = tuple(int(a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def bezier(p0, p1, p2, p3, steps=12):
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        points.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                       u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
    return points


class Sunflower:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0)
        self.canvas.pack()
        self.start = None
        self.seeds = []
        rng = random.Random(17)
        # Golden-angle seed pattern for the flower's rich, textured center.
        for i in range(590):
            radius = 94 * math.sqrt((i + 0.5) / 590)
            angle = i * 2.399963 + rng.uniform(-0.035, 0.035)
            self.seeds.append((radius * math.cos(angle), radius * math.sin(angle),
                               rng.uniform(1.2, 2.7), rng.choice(("#e4ae55", "#bd7436", "#f0c26a"))))
        self.motes = [(rng.uniform(30, W-30), rng.uniform(90, H-40),
                       rng.uniform(0.35, 1.2), rng.uniform(0, math.tau)) for _ in range(38)]
        self.draw_background()
        self.animate()

    def draw_background(self):
        c = self.canvas
        # A calm blue-to-honey sunset sky.
        for y in range(H):
            t = y / H
            color = mix("#17233d", "#e99a59", min(1, t * 1.22))
            c.create_line(0, y, W, y, fill=color)
        # Soft sun glow and distant hills.
        c.create_oval(630, 115, 790, 275, fill="#f8bb72", outline="")
        c.create_oval(652, 137, 768, 253, fill="#ffd38a", outline="")
        c.create_polygon(0, 470, 150, 390, 300, 465, 455, 385, 620, 465, 760, 400,
                         900, 455, 900, 700, 0, 700, fill="#435844", outline="")
        c.create_polygon(0, 520, 180, 465, 345, 520, 540, 455, 710, 515, 900, 455,
                         900, 700, 0, 700, fill="#293f38", outline="")
        # Little meadow lights.
        rng = random.Random(8)
        for _ in range(75):
            x, y = rng.randrange(W), rng.randrange(490, H)
            r = rng.choice((1, 2, 3))
            c.create_oval(x-r, y-r, x+r, y+r, fill=rng.choice(("#b6a46b", "#e7b66c", "#748759")), outline="")

    def transform(self, x, y, angle, scale=1):
        return (CX + (x*math.cos(angle) - y*math.sin(angle))*scale,
                CY + (x*math.sin(angle) + y*math.cos(angle))*scale)

    def petal(self, angle, length, width, color, sway, bloom, inner=False):
        c = self.canvas
        # Tapered, gently curved petal outline in its own radial coordinates.
        root, tip = 47, 47 + length * bloom
        w = width * bloom
        top = bezier((root, 0), (root + length*.25*bloom, -w*.72),
                     (root + length*.77*bloom, -w*.58), (tip, 0))
        bottom = bezier((tip, 0), (root + length*.77*bloom, w*.58),
                        (root + length*.25*bloom, w*.72), (root, 0))
        points = [self.transform(x, y, angle + sway) for x, y in top + bottom]
        flat = [v for p in points for v in p]
        c.create_polygon(*flat, fill=color, outline="#a95a24", width=1, smooth=True, tags="animation")
        # A slim sunlit center line gives each petal a soft, dimensional finish.
        if bloom > .35:
            vein = bezier((root+7, 0), (root+length*.35*bloom, -1),
                          (root+length*.72*bloom, -1), (tip-8, 0), 8)
            vein_points = [self.transform(x, y, angle+sway) for x, y in vein]
            c.create_line(*[v for p in vein_points for v in p], fill="#ffe58c", width=1.3, smooth=True, tags="animation")

    def leaf(self, x, y, angle, size, sway):
        c = self.canvas
        p0 = (x, y)
        tip = (x + math.cos(angle)*size, y + math.sin(angle)*size)
        side = math.pi/2
        p1 = (x + math.cos(angle)*size*.35 + math.cos(angle+side)*size*.24,
              y + math.sin(angle)*size*.35 + math.sin(angle+side)*size*.24)
        p2 = (x + math.cos(angle)*size*.82 + math.cos(angle+side)*size*.16,
              y + math.sin(angle)*size*.82 + math.sin(angle+side)*size*.16)
        p3 = (x + math.cos(angle)*size*.35 - math.cos(angle+side)*size*.24,
              y + math.sin(angle)*size*.35 - math.sin(angle+side)*size*.24)
        p4 = (x + math.cos(angle)*size*.82 - math.cos(angle+side)*size*.16,
              y + math.sin(angle)*size*.82 - math.sin(angle+side)*size*.16)
        outline = bezier(p0, p1, p2, tip, 14) + bezier(tip, p4, p3, p0, 14)
        pts = [self.transform(a, b, sway*.35) for a, b in outline]
        c.create_polygon(*[v for p in pts for v in p], fill="#557b43", outline="#9eb66a", width=1, smooth=True, tags="animation")
        mid = bezier(p0, (x+math.cos(angle)*size*.3, y+math.sin(angle)*size*.3),
                     (x+math.cos(angle)*size*.7, y+math.sin(angle)*size*.7), tip, 12)
        mid = [self.transform(a, b, sway*.35) for a, b in mid]
        c.create_line(*[v for p in mid for v in p], fill="#bdc77a", width=1.5, smooth=True, tags="animation")

    def animate(self):
        c = self.canvas
        c.delete("animation")
        if self.start is None:
            self.start = self.root.tk.call("clock", "milliseconds")
        t = (self.root.tk.call("clock", "milliseconds") - self.start) / 1000
        bloom = min(1, max(0, (t - .3) / 2.4))
        bloom = 1 - (1 - bloom) ** 3
        sway = math.sin(t * 1.15) * .035

        # The curved stem and two broad, veined leaves.
        c.create_line(CX, CY+55, CX+7, 460, CX+20, 660, fill="#426b3f", width=15,
                      smooth=True, capstyle=tk.ROUND, tags="animation")
        self.leaf(-4, 150, math.radians(202), 155, sway)
        self.leaf(9, 230, math.radians(-28), 145, sway)
        # Small leaf glints along the stem.
        c.create_line(CX-1, 390, CX+5, 645, fill="#82964e", width=2, smooth=True, tags="animation")

        # A light breeze moves the whole flower head by a few degrees.
        for i in range(24):
            a = math.tau * i / 24 + sway
            self.petal(a, 165 + 13*math.sin(i*3.1), 28 + 4*math.sin(i*1.7),
                       "#e9a528" if i % 3 else "#f3b638", sway, bloom)
        for i in range(20):
            a = math.tau * (i + .5) / 20 - sway*.4
            self.petal(a, 135 + 10*math.sin(i*2.4), 24, "#ffd34f" if i % 4 else "#ffc33b",
                       sway, bloom)

        # Velvet-brown disk, rim, and hundreds of tiny seed-like flecks.
        cx, cy = CX, CY
        c.create_oval(cx-108, cy-108, cx+108, cy+108, fill="#82431f", outline="#d88a2c", width=7, tags="animation")
        c.create_oval(cx-99, cy-99, cx+99, cy+99, fill="#59301f", outline="#e7a947", width=3, tags="animation")
        for x, y, r, color in self.seeds:
            # Gentle head sway, keeping the seed texture attached to the flower.
            px, py = x*math.cos(sway)-y*math.sin(sway), x*math.sin(sway)+y*math.cos(sway)
            c.create_oval(cx+px-r, cy+py-r, cx+px+r, cy+py+r, fill=color, outline="", tags="animation")
        c.create_oval(cx-9, cy-9, cx+9, cy+9, fill="#f2bd61", outline="", tags="animation")

        # Floating pollen catches the sunset light.
        for x, y, speed, phase in self.motes:
            px = x + math.sin(t*.7 + phase)*12
            py = (y - (t*18*speed) % 740) % H
            r = 1.5 + (math.sin(t*2 + phase)+1)*1.2
            c.create_oval(px-r, py-r, px+r, py+r, fill="#ffe49b", outline="", tags="animation")

        # A quiet dedication in the sunset sky.
        c.create_text(CX, 30, text="FOR MY SWEETHEAR", fill="#ffe8b0",
                      font=("Georgia", 12, "bold"), tags="animation")
        c.create_rectangle(0, 610, W, H, fill="#1d342f", outline="", tags="animation")
        c.create_line(90, 610, W-90, 610, fill="#d49a51", width=2, tags="animation")
        c.create_text(CX, 639, text="You make my world bloom.", fill="#fff2d6",
                      font=("Georgia", 23, "italic"), tags="animation")
        c.create_text(CX, 677, text="✦   a little flower, just for you   ✦", fill="#f2d9a8",
                      font=("Georgia", 11, "italic"), tags="animation")
        self.root.after(33, self.animate)


if __name__ == "__main__":
    window = tk.Tk()
    window.title("For My Sweetheart 🌻")
    window.resizable(False, False)
    Sunflower(window)
    window.mainloop()



