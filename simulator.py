"""Симулятор спутника: орбита, телеметрия, модули, команды."""
import math, random, time

MU, RE, WARP = 398600.4418, 6371.0, 30   # WARP — ускорение времени (1 сек = 30 сек орбиты)
GS = (55.75, 37.62)                       # наземная станция (Москва)

MODULES = {
    "power":   "Питание",
    "thermal": "Терморегуляция",
    "comms":   "Связь",
    "adcs":    "Ориентация",
    "engine":  "Двигатель",
    "camera":  "Камера",
}

class Satellite:
    def __init__(s):
        s.alt, s.inc = 420.0, math.radians(51.6)
        s.u = s.t = 0.0
        s.lon0 = 30.0
        s.battery, s.temp, s.fuel = 80.0, 20.0, 100.0
        s.panels, s.photo_left, s.photos = False, 0, 0
        s.faults = set()          # модули с аварией
        s.log = []
        s.say("info", "Спутник на орбите, связь установлена")

    # ---- орбита ----
    @property
    def r(s): return RE + s.alt
    @property
    def speed(s): return math.sqrt(MU / s.r)
    @property
    def period(s): return 2 * math.pi * math.sqrt(s.r ** 3 / MU)

    def pos(s, u, t):
        lat = math.asin(math.sin(s.inc) * math.sin(u))
        lon = math.atan2(math.cos(s.inc) * math.sin(u), math.cos(u)) \
              - 7.292e-5 * t + math.radians(s.lon0)
        return math.degrees(lat), (math.degrees(lon) + 180) % 360 - 180

    def track(s, n=120):
        return [s.pos(s.u + 2 * math.pi * k / n, s.t + s.period * k / n)
                for k in range(n + 1)]

    def elevation(s, lat, lon):
        la, lo, gl, go = map(math.radians, (lat, lon, *GS))
        cosg = math.sin(la) * math.sin(gl) + math.cos(la) * math.cos(gl) * math.cos(lo - go)
        g = math.acos(max(-1, min(1, cosg)))
        return math.degrees(math.atan2(cosg - RE / s.r, math.sin(g)))

    # ---- шаг симуляции (вызывать раз в секунду) ----
    def step(s):
        sim = WARP
        s.u = (s.u + 2 * math.pi / s.period * sim) % (2 * math.pi)
        s.t += sim
        s.sun = math.cos(s.u) > -0.6
        gen = (0.6 if s.panels else 0.2) if s.sun else 0
        load = 0.15 + (0.3 if s.photo_left > 0 else 0)
        s.battery = max(0, min(100, s.battery + gen - load))
        target = (40 if s.sun else -15) + (5 if s.panels else 0) + (3 if s.photo_left else 0)
        s.temp += (target - s.temp) * 0.05 + random.uniform(-.2, .2)
        if s.photo_left > 0:
            s.photo_left -= 1
            if s.photo_left == 0:
                s.photos += 1; s.say("ok", f"Снимок #{s.photos} сохранён")
        if random.random() < 0.004 and len(s.faults) < 2:   # случайные отказы
            m = random.choice(["engine", "comms", "adcs", "camera"])
            if m not in s.faults:
                s.faults.add(m); s.say("err", f"Отказ модуля: {MODULES[m]}")

    # ---- статусы ----
    def modules(s, signal):
        st = {k: ("ok", "Норма") for k in MODULES}
        if s.battery < 5: st["power"] = ("error", "Разряд критический")
        elif s.battery < 20: st["power"] = ("warn", "Низкий заряд")
        elif not s.panels: st["power"] = ("warn", "Панели не раскрыты")
        if s.temp > 60 or s.temp < -30: st["thermal"] = ("warn", "Выход за диапазон")
        if signal == 0: st["comms"] = ("warn", "Вне зоны станции")
        if s.photo_left: st["camera"] = ("on", "Съёмка...")
        for m in s.faults: st[m] = ("error", "Отказ")
        if s.fuel < 10: st["engine"] = ("warn", "Мало топлива")
        return {k: {"name": MODULES[k], "status": v[0], "note": v[1]} for k, v in st.items()}

    def snapshot(s):
        lat, lon = s.pos(s.u, s.t)
        el = s.elevation(lat, lon)
        signal = 0 if (el < 5 or "comms" in s.faults) else round(30 + 70 * math.sin(math.radians(el)))
        return {
            "lat": lat, "lon": lon, "alt": round(s.alt, 1),
            "speed": round(s.speed, 2), "period": round(s.period / 60, 1),
            "battery": round(s.battery, 1), "temp": round(s.temp, 1),
            "signal": signal, "fuel": round(s.fuel, 1), "sun": s.sun,
            "panels": s.panels, "photos": s.photos,
            "modules": s.modules(signal), "log": s.log[-8:], "gs": GS,
        }

    # ---- команды ----
    def say(s, level, msg):
        s.log.append({"time": time.strftime("%H:%M:%S"), "level": level, "msg": msg})

    def command(s, cmd, arg=None):
        if cmd == "deploy_panels":
            if s.panels: return s._r(False, "Панели уже раскрыты")
            s.panels = True; return s._r(True, "Солнечные батареи раскрыты")
        if cmd == "take_photo":
            if "camera" in s.faults: return s._r(False, "Камера неисправна")
            if s.photo_left: return s._r(False, "Камера занята")
            s.photo_left = 3; return s._r(True, "Съёмка запущена")
        if cmd == "boost_orbit":
            if "engine" in s.faults: return s._r(False, "Двигатель неисправен")
            if s.fuel < 5: return s._r(False, "Недостаточно топлива")
            s.alt += 10; s.fuel -= 5; return s._r(True, "Манёвр: орбита +10 км")
        if cmd == "reboot":
            if arg not in MODULES: return s._r(False, "Неизвестный модуль")
            s.faults.discard(arg); return s._r(True, f"Перезагрузка: {MODULES[arg]}")
        if cmd == "inject_fault":   # для демонстрации жюри
            s.faults.add(arg if arg in MODULES else "engine")
            return s._r(False, f"Имитация отказа: {MODULES.get(arg, 'Двигатель')}")
        return s._r(False, "Неизвестная команда")

    def _r(s, ok, msg):
        s.say("ok" if ok else "err", msg); return {"ok": ok, "message": msg}
