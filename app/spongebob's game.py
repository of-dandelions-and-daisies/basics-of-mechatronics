import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import serial
import serial.tools.list_ports
import threading
import time

# ── Palette ──────────────────────────────────────────────────────────────────
BG        = "#0077B6"   # ocean blue
PANEL     = "#023E8A"   # deep blue
YELLOW    = "#FFD700"   # spongebob yellow
YELLOW_DK = "#C8A800"
GREEN     = "#57CC99"   # start green
RED       = "#EF476F"   # stop red
CYAN      = "#90E0EF"   # light blue text
WHITE     = "#FFFFFF"
BROWN     = "#7A4100"   # text on yellow

FONT_TITLE  = ("Helvetica", 20, "bold")
FONT_LABEL  = ("Helvetica", 10, "bold")
FONT_BTN    = ("Helvetica", 12, "bold")
FONT_SMALL  = ("Helvetica", 9)
FONT_MONO   = ("Courier", 10)


class BallMachineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SpongeBob's Crazy Ride — Control Panel")
        self.root.configure(bg=BG)
        self.root.geometry("700x680")
        self.root.resizable(False, False)

        self.serial_conn = None
        self.connected   = False
        self.sim_mode    = False
        self.read_thread = None
        self.running     = False

        self._build_ui()

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── header ──
        hdr = tk.Frame(self.root, bg=YELLOW, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🧽  SpongeBob's Crazy Ride", font=FONT_TITLE,
                 bg=YELLOW, fg=BROWN).pack()
        tk.Label(hdr, text="Mechatronics Project — PC Control Panel",
                 font=FONT_SMALL, bg=YELLOW, fg=BROWN).pack()

        # ── connection bar ──
        conn_bar = tk.Frame(self.root, bg=PANEL, pady=8, padx=14)
        conn_bar.pack(fill="x")

        tk.Label(conn_bar, text="COM Port:", font=FONT_LABEL,
                 bg=PANEL, fg=CYAN).grid(row=0, column=0, padx=(0,6))

        self.port_var = tk.StringVar()
        self.port_cb  = ttk.Combobox(conn_bar, textvariable=self.port_var,
                                     width=10, state="readonly")
        self.port_cb.grid(row=0, column=1, padx=(0,6))
        self._refresh_ports()

        tk.Button(conn_bar, text="⟳", font=FONT_LABEL, bg=PANEL, fg=CYAN,
                  relief="flat", cursor="hand2",
                  command=self._refresh_ports).grid(row=0, column=2, padx=(0,12))

        tk.Label(conn_bar, text="Baud:", font=FONT_LABEL,
                 bg=PANEL, fg=CYAN).grid(row=0, column=3, padx=(0,6))
        self.baud_var = tk.StringVar(value="9600")
        ttk.Combobox(conn_bar, textvariable=self.baud_var,
                     values=["9600","19200","38400","57600","115200"],
                     width=8, state="readonly").grid(row=0, column=4, padx=(0,12))

        self.conn_btn = tk.Button(conn_bar, text="Connect", font=FONT_LABEL,
                                  bg=GREEN, fg=BROWN, relief="flat",
                                  padx=12, pady=4, cursor="hand2",
                                  command=self._toggle_connect)
        self.conn_btn.grid(row=0, column=5, padx=(0,6))

        self.sim_btn = tk.Button(conn_bar, text="🧪 Simulate", font=FONT_LABEL,
                                 bg="#FF6B35", fg=WHITE, relief="flat",
                                 padx=10, pady=4, cursor="hand2",
                                 command=self._toggle_simulate)
        self.sim_btn.grid(row=0, column=6, padx=(0,12))

        self.conn_dot = tk.Label(conn_bar, text="●", font=("Helvetica",16),
                                 bg=PANEL, fg="#555555")
        self.conn_dot.grid(row=0, column=7)
        self.conn_lbl = tk.Label(conn_bar, text="Disconnected",
                                 font=FONT_SMALL, bg=PANEL, fg=CYAN)
        self.conn_lbl.grid(row=0, column=8, padx=(4,0))

        # ── main content ──
        content = tk.Frame(self.root, bg=BG, padx=14, pady=10)
        content.pack(fill="both", expand=True)

        left  = tk.Frame(content, bg=BG)
        right = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right.pack(side="right", fill="both", expand=True)

        # ── left: controls ──
        self._section(left, "Controls")

        btn_grid = tk.Frame(left, bg=BG)
        btn_grid.pack(fill="x", pady=(0,10))

        self.btn_start    = self._ctrl_btn(btn_grid, "▶  Start",    GREEN,  BROWN, lambda: self._send("START"))
        self.btn_stop     = self._ctrl_btn(btn_grid, "■  Stop",     RED,    WHITE, lambda: self._send("STOP"))
        self.btn_dispense = self._ctrl_btn(btn_grid, "⊕  Dispense", YELLOW, BROWN, lambda: self._send("DISPENSE"))

        self.btn_start.grid   (row=0, column=0, padx=4, pady=4, sticky="ew")
        self.btn_stop.grid    (row=0, column=1, padx=4, pady=4, sticky="ew")
        self.btn_dispense.grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky="ew")
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # dispenser mode panel
        self._section(left, "System Mode")
        disp_fr = self._panel(left)
        self.disp_mode = tk.StringVar(value="MANUAL")

        tk.Label(disp_fr, text="How should the machine be controlled?",
                 font=FONT_LABEL, bg=PANEL, fg=CYAN).grid(
                 row=0, column=0, columnspan=2, sticky="w", pady=(0,8))

        self.disp_manual_rb = tk.Radiobutton(
            disp_fr, text="Manual  — app controls everything",
            variable=self.disp_mode, value="MANUAL",
            font=FONT_SMALL, bg=PANEL, fg=WHITE,
            selectcolor=PANEL, activebackground=PANEL,
            activeforeground=YELLOW, cursor="hand2",
            command=self._on_disp_mode_change)
        self.disp_manual_rb.grid(row=1, column=0, sticky="w", pady=2)

        self.disp_auto_rb = tk.Radiobutton(
            disp_fr, text="Auto  — physical switch controls everything",
            variable=self.disp_mode, value="AUTO",
            font=FONT_SMALL, bg=PANEL, fg=WHITE,
            selectcolor=PANEL, activebackground=PANEL,
            activeforeground=YELLOW, cursor="hand2",
            command=self._on_disp_mode_change)
        self.disp_auto_rb.grid(row=2, column=0, sticky="w", pady=2)

        self.disp_mode_lbl = tk.Label(disp_fr, text="Mode: MANUAL",
                                      font=FONT_LABEL, bg=PANEL, fg=YELLOW)
        self.disp_mode_lbl.grid(row=3, column=0, sticky="w", pady=(8,0))


        # mechanism status display
        self._section(left, "Mechanism Status")
        status_fr = self._panel(left)
        self.mech_states = {}
        mechanisms = [
            ("Lifter",    "LIFT"),
            ("Shooter",   "SHOOT"),
            ("Sorter",    "SORT"),
            ("Dispenser", "DISP"),
        ]
        for i, (label, key) in enumerate(mechanisms):
            tk.Label(status_fr, text=label, font=FONT_LABEL,
                     bg=PANEL, fg=CYAN, width=10, anchor="w").grid(
                         row=i, column=0, pady=5, sticky="w")
            dot = tk.Label(status_fr, text="●", font=("Helvetica", 18),
                           bg=PANEL, fg="#555555")
            dot.grid(row=i, column=1, padx=(6,4))
            state_lbl = tk.Label(status_fr, text="IDLE", font=FONT_LABEL,
                                 bg=PANEL, fg="#888888", width=8, anchor="w")
            state_lbl.grid(row=i, column=2, sticky="w")
            self.mech_states[key] = {"dot": dot, "label": state_lbl}

        # ── right: game info + status + custom cmd ──
        self._section(right, "Game")
        game_fr = self._panel(right)

        tk.Label(game_fr, text="Score", font=FONT_LABEL,
                 bg=PANEL, fg=CYAN).grid(row=0, column=0, sticky="w", padx=(0,10))
        self.score_label = tk.Label(game_fr, text="SCORE: 0", font=FONT_TITLE,
                                    bg=PANEL, fg=YELLOW)
        self.score_label.grid(row=0, column=1, sticky="w")

        tk.Label(game_fr, text="Last ball", font=FONT_LABEL,
                 bg=PANEL, fg=CYAN).grid(row=1, column=0, sticky="w", pady=(8,0))
        self.ball_label = tk.Label(game_fr, text="—", font=FONT_LABEL,
                                   bg=PANEL, fg=WHITE)
        self.ball_label.grid(row=1, column=1, sticky="w", pady=(8,0))

        tk.Label(game_fr, text="Result", font=FONT_LABEL,
                 bg=PANEL, fg=CYAN).grid(row=2, column=0, sticky="w", pady=(6,0))
        self.result_label = tk.Label(game_fr, text="—", font=FONT_LABEL,
                                     bg=PANEL, fg=WHITE)
        self.result_label.grid(row=2, column=1, sticky="w", pady=(6,0))

        self._section(right, "Status Feed")
        self.log_box = scrolledtext.ScrolledText(
            right, height=18, width=32, font=FONT_MONO,
            bg="#001D3D", fg=CYAN, insertbackground=CYAN,
            relief="flat", state="disabled", wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, pady=(0,10))

        self._section(right, "Custom Command")
        cmd_fr = tk.Frame(right, bg=BG)
        cmd_fr.pack(fill="x")
        self.cmd_entry = tk.Entry(cmd_fr, font=FONT_MONO,
                                  bg="#001D3D", fg=CYAN,
                                  insertbackground=CYAN, relief="flat")
        self.cmd_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0,6))
        self.cmd_entry.bind("<Return>", lambda e: self._send_custom())
        tk.Button(cmd_fr, text="Send", font=FONT_LABEL,
                  bg=YELLOW, fg=BROWN, relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=self._send_custom).pack(side="right")

        # ── footer ──
        ft = tk.Frame(self.root, bg=PANEL, pady=6)
        ft.pack(fill="x", side="bottom")
        tk.Label(ft, text="SpongeBob's Crazy Ride v1.0  •  HC-06 Bluetooth  •  9600 baud",
                 font=FONT_SMALL, bg=PANEL, fg=CYAN).pack()

        self._set_controls_state("disabled")

    # ── helpers ──────────────────────────────────────────────────────────────

    def _section(self, parent, text):
        tk.Label(parent, text=text.upper(), font=FONT_LABEL,
                 bg=BG, fg=CYAN).pack(anchor="w", pady=(8,2))

    def _panel(self, parent):
        fr = tk.Frame(parent, bg=PANEL, padx=10, pady=8)
        fr.pack(fill="x", pady=(0,6))
        return fr

    def _ctrl_btn(self, parent, text, color, fg, cmd):
        return tk.Button(parent, text=text, font=FONT_BTN,
                         bg=color, fg=fg, relief="flat",
                         padx=8, pady=12, cursor="hand2", command=cmd)

    def _set_controls_state(self, state):
        for rb in [self.disp_manual_rb, self.disp_auto_rb]:
            rb.config(state=state)
        if state == "disabled":
            for btn in [self.btn_start, self.btn_stop, self.btn_dispense]:
                btn.config(state="disabled")
        else:
            # respect current mode when re-enabling
            if self.disp_mode.get() == "AUTO":
                for btn in [self.btn_start, self.btn_stop, self.btn_dispense]:
                    btn.config(state="disabled")
            else:
                for btn in [self.btn_start, self.btn_stop, self.btn_dispense]:
                    btn.config(state="normal")

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports
        if ports:
            self.port_var.set(ports[0])

    def _on_disp_mode_change(self):
        mode = self.disp_mode.get()
        self.disp_mode_lbl.config(text=f"Mode: {mode}")
        if mode == "AUTO":
            # gray out all manual controls — physical switch takes over
            for btn in [self.btn_start, self.btn_stop, self.btn_dispense]:
                btn.config(state="disabled")
            self._send("SYS:MODE:AUTO")
        else:
            # restore manual controls
            for btn in [self.btn_start, self.btn_stop, self.btn_dispense]:
                btn.config(state="normal")
            self._send("SYS:MODE:MANUAL")

    # ── simulation ────────────────────────────────────────────────────────────

    def _toggle_simulate(self):
        if not self.sim_mode:
            # enter sim mode
            self.sim_mode  = True
            self.connected = True
            self.sim_btn.config(text="⏹ Stop Sim", bg=RED)
            self.conn_dot.config(fg="#FF6B35")
            self.conn_lbl.config(text="Simulation mode — no hardware needed")
            self._set_controls_state("normal")
            self._log("🧪 Simulation mode ON — buttons will show fake Arduino replies")
            self._log("← STATUS:READY")
        else:
            # exit sim mode
            self.sim_mode  = False
            self.connected = False
            self.sim_btn.config(text="🧪 Simulate", bg="#FF6B35")
            self.conn_dot.config(fg="#555555")
            self.conn_lbl.config(text="Disconnected")
            self._set_controls_state("disabled")
            self._log("🧪 Simulation mode OFF")

    # fake replies the simulated Arduino would send back
    SIM_REPLIES = {
        "START":            ["STATUS:RUNNING", "LIFT:ON", "SHOOT:ON", "SORT:ON",
                             "BALL:YELLOW", "GAME:CORRECT", "SCORE:1"],
        "STOP":             ["STATUS:IDLE", "LIFT:OFF", "SHOOT:OFF", "SORT:OFF", "DISP:OFF"],
        "DISPENSE":         ["DISP:ON", "BALL:DISPENSED", "DISP:OFF",
                             "BALL:PINK", "GAME:WRONG", "SCORE:0"],
        "SYS:MODE:AUTO":    ["SYS:MODE:AUTO:OK"],
        "SYS:MODE:MANUAL":  ["SYS:MODE:MANUAL:OK"],
    }

    def _sim_reply(self, cmd):
        key = cmd.strip()
        replies = self.SIM_REPLIES.get(key, [f"ACK:{key}"])
        delay = 300
        for r in replies:
            self.root.after(delay, self._log, f"← {r}")
            self.root.after(delay, self._parse_incoming, r)
            delay += 350

    def _parse_incoming(self, msg):
        """Update UI from incoming Arduino messages"""
        # mechanism dot indicators
        STATE_COLORS = {"ON": (GREEN, "RUNNING"), "OFF": ("#555555", "IDLE")}
        for key in self.mech_states:
            if msg.startswith(f"{key}:"):
                state = msg.split(":")[1].upper()
                color, text = STATE_COLORS.get(state, ("#FFD700", state))
                self.mech_states[key]["dot"].config(fg=color)
                self.mech_states[key]["label"].config(text=text, fg=color)
                return

        # ball color detection
        if msg == "BALL:PINK":
            self.ball_label.config(text="🟣 Pink ball", fg="#FF69B4")
            self._log("Pink ball detected")
        elif msg == "BALL:YELLOW":
            self.ball_label.config(text="🟡 Yellow ball", fg=YELLOW)
            self._log("Yellow ball detected")

        # game result
        elif msg == "GAME:CORRECT":
            self.result_label.config(text="✓ Correct!", fg=GREEN)
            self._log("✓ Correct answer!")
        elif msg == "GAME:WRONG":
            self.result_label.config(text="✗ Wrong!", fg=RED)
            self._log("✗ Wrong answer!")

        # score update — Arduino sends e.g. "SCORE:7"
        elif msg.startswith("SCORE:"):
            self.score_label.config(text=msg)   # displays "SCORE:7"
            self._log(f"Score updated: {msg}")

    # ── connection ────────────────────────────────────────────────────────────

    def _toggle_connect(self):
        if not self.connected:
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            if not port:
                messagebox.showerror("No port", "Select a COM port first.")
                return
            try:
                self.serial_conn = serial.Serial(port, baud, timeout=1)
                self.connected   = True
                self.conn_btn.config(text="Disconnect", bg=RED, fg=WHITE)
                self.conn_dot.config(fg=GREEN)
                self.conn_lbl.config(text=f"Connected — {port} @ {baud}")
                self._set_controls_state("normal")
                self._log(f"✓ Connected to {port} at {baud} baud")
                self._start_reader()
            except Exception as e:
                messagebox.showerror("Connection failed", str(e))
        else:
            self._disconnect()

    def _disconnect(self):
        self.connected = False
        if self.serial_conn:
            self.serial_conn.close()
        self.conn_btn.config(text="Connect", bg=GREEN, fg=BROWN)
        self.conn_dot.config(fg="#555555")
        self.conn_lbl.config(text="Disconnected")
        self._set_controls_state("disabled")
        self._log("✗ Disconnected")

    # ── serial read thread ────────────────────────────────────────────────────

    def _start_reader(self):
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

    def _read_loop(self):
        while self.connected and self.serial_conn:
            try:
                if self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
                    if line:
                        self.root.after(0, self._log, f"← {line}")
                        self.root.after(0, self._parse_incoming, line)
            except:
                self.root.after(0, self._disconnect)
                break
            time.sleep(0.05)

    # ── send ──────────────────────────────────────────────────────────────────

    def _send(self, cmd):
        if not self.connected:
            return
        self._log(f"→ {cmd}")
        if self.sim_mode:
            self._sim_reply(cmd)
            return
        try:
            self.serial_conn.write((cmd + "\n").encode("utf-8"))
        except Exception as e:
            self._log(f"! Error: {e}")

    def _send_custom(self):
        cmd = self.cmd_entry.get().strip()
        if cmd:
            self._send(cmd)
            self.cmd_entry.delete(0, "end")


    # ── log ───────────────────────────────────────────────────────────────────

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_box.config(state="normal")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = BallMachineGUI(root)
    root.mainloop()
