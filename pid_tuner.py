import tkinter as tk
import warnings
import webbrowser  # Allows us to open links in the browser
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from scipy import signal

# --- CONFIGURATION ---
DEVELOPER_NAME = "Rabah"
LINK_URL = "https://github.com/rabahdj2002"  # Your profile based on our history
SIM_DEBOUNCE_MS = 150  # Delay before re-simulating after a slider move


def parse_coeffs(text):
    """Parse a '1 2 10' (or '1, 2, 10') coefficient string into floats.

    Returns the list of coefficients, [] for empty input, or None if
    the text cannot be parsed.
    """
    cleaned = text.replace(',', ' ').strip()
    if not cleaned:
        return []
    try:
        return [float(x) for x in cleaned.split()]
    except ValueError:
        return None


def format_poly(coeffs):
    """Format coefficients as a polynomial string, e.g. 's^2 + 0.5s + 2'."""
    if not coeffs:
        return "0"
    terms = []
    power = len(coeffs) - 1
    for i, c in enumerate(coeffs):
        if c == 0:
            power -= 1
            continue

        # Make the number pretty (remove trailing zeros)
        c_str = f"{c:.2f}".rstrip('0').rstrip('.')

        # Build the s^n part
        if power == 0:
            term = f"{c_str}"
        elif power == 1:
            term = f"{c_str}s"
        else:
            term = f"{c_str}s^{power}"

        # Handle Signs
        if i > 0 and c > 0:
            terms.append(f"+ {term}")
        elif c < 0:
            terms.append(f"- {term.replace('-', '')}")
        else:
            terms.append(term)
        power -= 1
    return " ".join(terms) if terms else "0"


def closed_loop_tf(plant_num, plant_den, kp, ki, kd):
    """Closed-loop transfer function for unity feedback PID * Plant.

    Returns (num, den) coefficient arrays for T(s) = C(s)G(s) / (1 + C(s)G(s)).
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Controller C(s) = (Kd*s^2 + Kp*s + Ki) / s
        pid_num = [kd, kp, ki]
        pid_den = [1, 0]

        sys_Plant = signal.TransferFunction(plant_num, plant_den)
        sys_PID = signal.TransferFunction(pid_num, pid_den)

        # Multiply: Open Loop = PID * Plant
        open_num = signal.convolve(sys_Plant.num, sys_PID.num)
        open_den = signal.convolve(sys_Plant.den, sys_PID.den)

        # Feedback: Closed Loop = Open / (1 + Open)
        # Algebra: T(s) = Num_Open / (Den_Open + Num_Open)

        # Align array lengths (pad with zeros) for addition — handle
        # both directions so high-derivative plants don't crash here
        if len(open_num) < len(open_den):
            open_num = np.pad(open_num, (len(open_den) - len(open_num), 0), 'constant')
        elif len(open_den) < len(open_num):
            open_den = np.pad(open_den, (len(open_num) - len(open_den), 0), 'constant')

        closed_num = open_num
        closed_den = open_den + open_num

        sys_Closed = signal.TransferFunction(closed_num, closed_den)
        return sys_Closed.num, sys_Closed.den


def step_response(num, den, t_max, points=1000):
    """Compute the step response of a transfer function. Returns (t, y)."""
    t_span = np.linspace(0, t_max, points)
    sys_closed = signal.TransferFunction(num, den)
    t, y = signal.step(sys_closed, T=t_span)
    return t, y


class PIDSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title(f"PID Control Dashboard - {DEVELOPER_NAME}")
        self._after_id = None

        # We use a 'style' to make the interface look a bit more modern
        style = ttk.Style()
        style.theme_use('clam')

        # --- MAIN LAYOUT ---
        # The app is split into two sides: Controls (Left) and Graphs (Right)
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left Side: The Control Panel
        control_panel = ttk.Frame(main_frame, padding="15")
        control_panel.pack(side=tk.LEFT, fill=tk.Y)

        # Right Side: The Simulation Plot
        plot_panel = ttk.Frame(main_frame, padding="10")
        plot_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ===============================================
        # SECTION 1: SYSTEM DEFINITION (The "Plant")
        # ===============================================
        sys_frame = ttk.LabelFrame(control_panel, text="Step 1: Define Your System", padding="10")
        sys_frame.pack(fill=tk.X, pady=(0, 15))

        # Instructions
        ttk.Label(sys_frame, text="Enter coefficients (e.g., '1 2 10' = 1s² + 2s + 10)",
                 font=("Segoe UI", 9), foreground="#555").pack(anchor=tk.W, pady=(0, 5))

        # Input: Numerator
        ttk.Label(sys_frame, text="Numerator:").pack(anchor=tk.W)
        self.num_input = ttk.Entry(sys_frame, font=('Consolas', 10))
        self.num_input.pack(fill=tk.X, pady=(0, 5))
        self.num_input.bind("<KeyRelease>", self.preview_equation) # Updates text as you type
        self.num_input.bind("<Return>", lambda e: self.run_simulation())

        # Input: Denominator
        ttk.Label(sys_frame, text="Denominator:").pack(anchor=tk.W)
        self.den_input = ttk.Entry(sys_frame, font=('Consolas', 10))
        self.den_input.pack(fill=tk.X, pady=(0, 10))
        self.den_input.bind("<KeyRelease>", self.preview_equation)
        self.den_input.bind("<Return>", lambda e: self.run_simulation())

        # The "Live Preview" Box
        self.preview_frame = ttk.Frame(sys_frame, borderwidth=1, relief="solid")
        self.preview_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(self.preview_frame, text="System G(s):", font=("Segoe UI", 8, "bold"), background="#eee").pack(fill=tk.X)
        self.equation_lbl = ttk.Label(self.preview_frame, text="Waiting for input...",
                                      font=('Consolas', 11, 'bold'), foreground="#0055aa", justify=tk.CENTER, background="#fff")
        self.equation_lbl.pack(fill=tk.X, pady=5)

        # Action Buttons
        btn_frame = ttk.Frame(sys_frame)
        btn_frame.pack(fill=tk.X)

        # Button to load the bouncy example
        ttk.Button(btn_frame, text="Load Example", command=self.load_example).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Button to confirm changes
        confirm_btn = ttk.Button(btn_frame, text="Apply Changes ✅", command=self.run_simulation)
        confirm_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ===============================================
        # SECTION 2: TUNING (The PID Knobs)
        # ===============================================
        tune_frame = ttk.LabelFrame(control_panel, text="Step 2: Tune Controller", padding="10")
        tune_frame.pack(fill=tk.X, pady=(0, 15))

        self.kp_var = self.add_slider(tune_frame, "Proportional (Kp)", 0, 100, 10)
        self.ki_var = self.add_slider(tune_frame, "Integral (Ki)", 0, 50, 0)
        self.kd_var = self.add_slider(tune_frame, "Derivative (Kd)", 0, 50, 5)

        # ===============================================
        # SECTION 3: SIMULATION SETTINGS
        # ===============================================
        sim_frame = ttk.LabelFrame(control_panel, text="Settings", padding="10")
        sim_frame.pack(fill=tk.X, pady=(0, 15))

        self.time_var = self.add_slider(sim_frame, "Duration (Seconds)", 1, 50, 10)

        # ===============================================
        # FOOTER: CREDITS
        # ===============================================
        footer_frame = ttk.Frame(control_panel)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        credit_lbl = ttk.Label(footer_frame, text=f"Developed by {DEVELOPER_NAME}",
                              cursor="hand2", font=("Segoe UI", 9, "underline"), foreground="blue")
        credit_lbl.pack()
        # Bind the click event to open the web browser
        credit_lbl.bind("<Button-1>", lambda e: webbrowser.open(LINK_URL))

        # ===============================================
        # PLOTTING AREA
        # ===============================================
        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Start with the example loaded
        self.load_example()

    def add_slider(self, parent, label_text, min_v, max_v, default_v):
        """Helper to create a nice slider row"""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=5)

        # Label
        ttk.Label(row, text=label_text, width=15).pack(side=tk.LEFT)

        # Variable
        var = tk.DoubleVar(value=default_v)

        # The Slider
        scale = ttk.Scale(row, from_=min_v, to=max_v, variable=var, orient=tk.HORIZONTAL,
                          command=lambda v: self.schedule_simulation())
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # The Value Readout
        val_lbl = ttk.Label(row, text=f"{default_v:.1f}", width=4)
        val_lbl.pack(side=tk.RIGHT)

        # Auto-update the text label when variable changes
        var.trace_add("write", lambda *args: val_lbl.config(text=f"{var.get():.1f}"))

        return var

    def schedule_simulation(self):
        """Debounce slider movement: re-simulate once dragging pauses."""
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(SIM_DEBOUNCE_MS, self._run_scheduled)

    def _run_scheduled(self):
        self._after_id = None
        self.run_simulation()

    def load_example(self):
        """Loads a classic Mass-Spring-Damper system"""
        self.num_input.delete(0, tk.END)
        self.num_input.insert(0, "1")

        self.den_input.delete(0, tk.END)
        self.den_input.insert(0, "1 0.5 2") # s^2 + 0.5s + 2

        self.preview_equation()
        self.run_simulation()

    def get_coefficients(self):
        """Reads the text boxes and converts strings to number arrays"""
        num = parse_coeffs(self.num_input.get())
        den = parse_coeffs(self.den_input.get())
        if num is None or den is None:
            return None, None
        # Forgiving defaults for empty boxes
        return (num or [0]), (den or [1])

    def preview_equation(self, event=None):
        """Updates the visual fraction without running the full simulation"""
        num, den = self.get_coefficients()

        if num is None or den is None:
            self.equation_lbl.config(text="Invalid Input", foreground="red")
            return

        n_text = format_poly(num)
        d_text = format_poly(den)

        # Draw the fraction bar using dashes
        bar = "-" * max(len(n_text), len(d_text))
        self.equation_lbl.config(text=f"{n_text}\n{bar}\n{d_text}", foreground="#0055aa")

    def run_simulation(self):
        """The brain: Calculates math and draws the graph"""
        # 1. Get the Plant System
        plant_num, plant_den = self.get_coefficients()
        if plant_num is None:
            return

        # 2. Get PID Settings
        Kp = self.kp_var.get()
        Ki = self.ki_var.get()
        Kd = self.kd_var.get()
        T_max = self.time_var.get()

        try:
            closed_num, closed_den = closed_loop_tf(plant_num, plant_den, Kp, Ki, Kd)
            t, y = step_response(closed_num, closed_den, T_max)

            # 3. Draw Plot
            self.ax.clear()

            # Plot the response curve
            self.ax.plot(t, y, linewidth=2.5, color='#007acc', label='System Output')

            # Plot the Target Line (Set Point)
            self.ax.axhline(y=1.0, color='#e74c3c', linestyle='--', linewidth=1.5, label='Target (Set Point)')

            # Styling
            self.ax.set_title("Step Response Simulation", fontsize=12, fontweight='bold')
            self.ax.set_xlabel("Time (seconds)")
            self.ax.set_ylabel("Amplitude")
            self.ax.set_xlim(0, T_max)
            self.ax.grid(True, linestyle=':', alpha=0.6)
            self.ax.legend(loc='lower right')

            self.canvas.draw()

            # Reset text color if it was red before
            self.equation_lbl.config(foreground="#0055aa")

        except Exception as e:  # noqa: BLE001 - any solver/input error is shown on the plot
            # If math explodes, show error on the plot
            self.ax.clear()
            self.ax.text(0.5, 0.5, f"Simulation Error:\n{e!s}",
                         ha='center', va='center', color='red', fontsize=12)
            self.canvas.draw()
            self.equation_lbl.config(foreground="red")

if __name__ == "__main__":
    root = tk.Tk()
    # Set a reasonable default size
    root.geometry("1100x750")
    app = PIDSimulator(root)
    root.mainloop()
