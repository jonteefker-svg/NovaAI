# ==============================================================================
# NOVA AI - Version 4.1
# ==============================================================================

import customtkinter as ctk
import json
import os
import threading
import datetime
import platform
import sys
import random
import requests

# ------------------------------------------------------------------------------
# API KEYS
# ------------------------------------------------------------------------------
GROQ_API_KEY   = "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"
OPENAI_API_KEY = "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"
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# DATEIPFADE
# ------------------------------------------------------------------------------
def get_data_dir():
    if platform.system() == "Darwin":
        d = os.path.expanduser("~/Library/Application Support/NOVA_AI")
    else:
        d = os.path.join(os.path.expanduser("~"), ".nova_ai")
    os.makedirs(d, exist_ok=True)
    return d

BASE_DIR      = get_data_dir()
HISTORY_FILE  = os.path.join(BASE_DIR, "nova_history.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "nova_settings.json")
LEARNING_FILE = os.path.join(BASE_DIR, "nova_learning.json")
LOG_FILE      = os.path.join(BASE_DIR, "debug_log.txt")

sys.stderr = open(LOG_FILE, "a")
sys.stdout = sys.stderr

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# ------------------------------------------------------------------------------
# MODELLE
# ------------------------------------------------------------------------------
PROVIDERS = {
    "Groq": [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    "Ollama (lokal)": [
        "llama3",
        "mistral",
        "gemma",
        "phi3",
        "llama2",
    ],
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
}

# ------------------------------------------------------------------------------
# PERSÖNLICHKEITEN & FARBEN
# ------------------------------------------------------------------------------
PERSONALITIES = {
    "🤖 Standard":  "Du bist Nova, eine kluge und hilfreiche KI-Assistentin. Du antwortest präzise, freundlich und auf Deutsch.",
    "😎 Lässig":    "Du bist Nova, eine coole und entspannte KI. Du redest locker, benutzt manchmal Slang, bist aber trotzdem hilfreich. Kurze, knackige Antworten.",
    "🎓 Professor": "Du bist Nova, eine sehr gelehrte KI. Du erklärst alles sehr detailliert und wissenschaftlich.",
    "😂 Witzig":    "Du bist Nova, eine witzige KI die gerne Witze macht. Du beantwortest trotzdem alle Fragen, aber mit einem Augenzwinkern.",
    "🧘 Ruhig":     "Du bist Nova, eine sehr ruhige, bedachte KI. Du antwortest besonnen und empathisch.",
    "⚡ Direkt":    "Du bist Nova. Kurz, direkt, auf den Punkt. Nur das Wesentliche.",
}

ACCENT_COLORS = {
    "Blau":   ("#3B8ED0", "#36719F"),
    "Pink":   ("#F55AA8", "#D1478E"),
    "Grün":   ("#2ECC71", "#27AE60"),
    "Orange": ("#E67E22", "#D35400"),
    "Lila":   ("#9B59B6", "#7D3C98"),
    "Rot":    ("#E74C3C", "#C0392B"),
}

DEFAULT_SETTINGS = {
    "personality":  "🤖 Standard",
    "accent_color": "Blau",
    "appearance":   "System",
    "multi_answer": True,
    "provider":     "Groq",
    "model": "llama-3.3-70b-versatile",
}

# ------------------------------------------------------------------------------
# API FUNKTIONEN
# ------------------------------------------------------------------------------
def ask_groq(messages, model):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "max_tokens": 1024},
        timeout=30
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def ask_openai(messages, model):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "max_tokens": 1024},
        timeout=30
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def ask_ollama(messages, model):
    import ollama
    client = ollama.Client(host='http://127.0.0.1:11434')
    resp   = client.chat(model=model, messages=messages)
    return resp['message']['content']

def ask_model(messages, provider, model):
    if provider == "Groq":
        return ask_groq(messages, model)
    elif provider == "OpenAI":
        return ask_openai(messages, model)
    elif provider == "Ollama (lokal)":
        return ask_ollama(messages, model)
    else:
        raise ValueError(f"Unbekannter Anbieter: {provider}")

# ------------------------------------------------------------------------------
# HAUPTKLASSE
# ------------------------------------------------------------------------------
class NovaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("✦ Nova AI 4.1")
        self.geometry("1200x860")
        self.minsize(900, 600)

        self.settings = self._load_json(SETTINGS_FILE) or {}
        for k, v in DEFAULT_SETTINGS.items():
            if k not in self.settings:
                self.settings[k] = v

        self.chat_history = self._load_json(HISTORY_FILE) or {}
        self.learning     = self._load_json(LEARNING_FILE) or {"preferred": {}}

        self.current_chat_id = str(datetime.datetime.now().timestamp())
        self.chat_history[self.current_chat_id] = []

        self.is_thinking       = False
        self._anim_angle       = 0
        self._pending_variants = []
        self._variant_buttons  = []

        acc = self.settings.get("accent_color", "Blau")
        self.accent_color, self.hover_color = ACCENT_COLORS.get(acc, ACCENT_COLORS["Blau"])

        ctk.set_appearance_mode(self.settings.get("appearance", "System"))

        self._build_ui()
        self.update_sidebar_list()
        self.animate()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_chat_area()
        self._build_input_area()

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="✦ NOVA AI", font=("Arial", 26, "bold")).pack(pady=(20,4))
        ctk.CTkLabel(self.sidebar, text="Version 4.1", font=("Arial", 11), text_color="gray").pack()

        self.canvas = ctk.CTkCanvas(self.sidebar, width=60, height=60,
                                     highlightthickness=0, bg="#2b2b2b", bd=0)
        self.canvas.pack(pady=8)

        self.settings_btn = ctk.CTkButton(self.sidebar, text="⚙️ Einstellungen",
                                           fg_color=self.accent_color, hover_color=self.hover_color,
                                           command=self.toggle_settings)
        self.settings_btn.pack(pady=(8,0), padx=16, fill="x")

        self.settings_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.settings_visible = False

        # Erscheinungsbild
        ctk.CTkLabel(self.settings_container, text="🌗 Erscheinungsbild", font=("Arial", 12, "bold")).pack(pady=(10,2), padx=16, anchor="w")
        self.mode_menu = ctk.CTkOptionMenu(self.settings_container,
                                            values=["System","Dark","Light"],
                                            command=self._change_mode)
        self.mode_menu.set(self.settings.get("appearance","System"))
        self.mode_menu.pack(pady=2, padx=16, fill="x")

        # Farbe
        ctk.CTkLabel(self.settings_container, text="🎨 Akzentfarbe", font=("Arial", 12, "bold")).pack(pady=(8,2), padx=16, anchor="w")
        self.color_menu = ctk.CTkOptionMenu(self.settings_container,
                                             values=list(ACCENT_COLORS.keys()),
                                             command=self.change_accent_color)
        self.color_menu.set(self.settings.get("accent_color","Blau"))
        self.color_menu.pack(pady=2, padx=16, fill="x")

        # Persönlichkeit
        ctk.CTkLabel(self.settings_container, text="🎭 Persönlichkeit", font=("Arial", 12, "bold")).pack(pady=(8,2), padx=16, anchor="w")
        self.personality_menu = ctk.CTkOptionMenu(self.settings_container,
                                                   values=list(PERSONALITIES.keys()),
                                                   command=self._change_personality)
        self.personality_menu.set(self.settings.get("personality","🤖 Standard"))
        self.personality_menu.pack(pady=2, padx=16, fill="x")

        # KI Anbieter 
        ctk.CTkLabel(self.settings_container, text="🧠 KI Anbieter", font=("Arial", 12, "bold")).pack(pady=(8,2), padx=16, anchor="w")
        self.provider_seg = ctk.CTkSegmentedButton(
            self.settings_container,
            values=["Groq", "Ollama (lokal)", "OpenAI"],
            command=self._change_provider
        )
        self.provider_seg.set(self.settings.get("provider","Groq"))
        self.provider_seg.pack(pady=2, padx=16, fill="x")

        # Modell 
        ctk.CTkLabel(self.settings_container, text="🤖 Modell", font=("Arial", 12, "bold")).pack(pady=(8,2), padx=16, anchor="w")
        current_provider = self.settings.get("provider","Groq")
        self.model_menu = ctk.CTkOptionMenu(
            self.settings_container,
            values=PROVIDERS[current_provider],
            command=self._change_model
        )
        self.model_menu.set(self.settings.get("model", PROVIDERS[current_provider][0]))
        self.model_menu.pack(pady=2, padx=16, fill="x")

        # Varianten
        ctk.CTkLabel(self.settings_container, text="🔀 Antwort-Varianten", font=("Arial", 12, "bold")).pack(pady=(8,2), padx=16, anchor="w")
        self.multi_var = ctk.BooleanVar(value=self.settings.get("multi_answer",True))
        ctk.CTkSwitch(self.settings_container, text="Nova gibt 2 Varianten",
                      variable=self.multi_var, command=self._save_settings).pack(pady=2, padx=16, anchor="w")

        # Aktionen
        ctk.CTkLabel(self.settings_container, text="🛠️ Aktionen", font=("Arial", 12, "bold")).pack(pady=(10,2), padx=16, anchor="w")
        self.copy_btn = ctk.CTkButton(self.settings_container, text="📋 Letzte Antwort kopieren",
                                       fg_color=self.accent_color, hover_color=self.hover_color,
                                       command=self.copy_last_answer)
        self.copy_btn.pack(pady=2, padx=16, fill="x")
        ctk.CTkButton(self.settings_container, text="📤 Chat exportieren (.txt)",
                      fg_color=self.accent_color, hover_color=self.hover_color,
                      command=self.export_chat).pack(pady=2, padx=16, fill="x")
        ctk.CTkButton(self.settings_container, text="🗑️ Alles löschen",
                      fg_color="#602020", hover_color="#8B0000",
                      command=self.clear_all_history).pack(pady=(4,8), padx=16, fill="x")

        # Suche
        ctk.CTkLabel(self.sidebar, text="🔍 Suche", font=("Arial", 12, "bold")).pack(pady=(12,2), padx=16, anchor="w")
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Suchen...")
        self.search_entry.pack(padx=16, fill="x")
        self.search_entry.bind("<KeyRelease>", lambda e: self.update_sidebar_list())

        self.new_chat_btn = ctk.CTkButton(self.sidebar, text="➕ Neuer Chat",
                                           fg_color=self.accent_color, hover_color=self.hover_color,
                                           command=self.new_chat)
        self.new_chat_btn.pack(pady=10, padx=16, fill="x")

        self.history_frame = ctk.CTkScrollableFrame(self.sidebar, label_text="📜 Chat-Verlauf")
        self.history_frame.pack(fill="both", expand=True, padx=10, pady=(0,10))

    def _build_chat_area(self):
        self.chat_display = ctk.CTkTextbox(self, state="disabled", corner_radius=15,
                                            font=("Arial", 15), wrap="word")
        self.chat_display.grid(row=0, column=1, padx=20, pady=(20,5), sticky="nsew")
        self.variants_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.variants_frame.grid(row=1, column=1, padx=20, pady=0, sticky="ew")

    def _build_input_area(self):
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=2, column=1, padx=20, pady=(5,20), sticky="ew")
        self.input_frame.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Schreib Nova etwas...",
                                   height=55, corner_radius=28, border_color=self.accent_color)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda e: self.send_message())
        self.send_button = ctk.CTkButton(self.input_frame, text="🚀", width=55, height=55,
                                          corner_radius=28, fg_color=self.accent_color,
                                          hover_color=self.hover_color, command=self.send_message)
        self.send_button.grid(row=0, column=1, padx=(10,0))

    # ------------------------------------------------------------------
    # EINSTELLUNGEN
    # ------------------------------------------------------------------
    def toggle_settings(self):
        if not self.settings_visible:
            self.settings_container.pack(after=self.settings_btn, fill="x")
            self.settings_btn.configure(text="🔼 Schließen")
            self.settings_visible = True
        else:
            self.settings_container.pack_forget()
            self.settings_btn.configure(text="⚙️ Einstellungen")
            self.settings_visible = False

    def _change_mode(self, mode):
        ctk.set_appearance_mode(mode)
        self.settings["appearance"] = mode
        self._save_settings()

    def _change_personality(self, p):
        self.settings["personality"] = p
        self._save_settings()
        self._show_status(f"Persönlichkeit: {p}")

    def _change_provider(self, provider):
        self.settings["provider"] = provider
        models = PROVIDERS[provider]
        self.model_menu.configure(values=models)
        self.model_menu.set(models[0])
        self.settings["model"] = models[0]
        self._save_settings()
        self._show_status(f"Anbieter: {provider} – Modell: {models[0]}")

    def _change_model(self, model):
        self.settings["model"] = model
        self._save_settings()
        self._show_status(f"Modell: {model}")

    def change_accent_color(self, color_name):
        main, hover = ACCENT_COLORS.get(color_name, ACCENT_COLORS["Blau"])
        self.accent_color = main
        self.hover_color  = hover
        self.settings["accent_color"] = color_name
        self._save_settings()
        for w in [self.new_chat_btn, self.send_button, self.copy_btn, self.settings_btn]:
            try: w.configure(fg_color=main, hover_color=hover)
            except: pass
        for w in [self.mode_menu, self.color_menu, self.personality_menu, self.model_menu]:
            try: w.configure(button_color=main, button_hover_color=hover)
            except: pass
        try: self.provider_seg.configure(selected_color=main, selected_hover_color=hover)
        except: pass
        self.entry.configure(border_color=main)

    def _save_settings(self):
        self.settings["multi_answer"] = self.multi_var.get()
        self._save_json(self.settings, SETTINGS_FILE)

    def _show_status(self, msg):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"ℹ️ {msg}\n\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    # ------------------------------------------------------------------
    # ANIMATION
    # ------------------------------------------------------------------
    def animate(self):
        self.canvas.delete("all")
        if self.is_thinking:
            self._anim_angle = (self._anim_angle + 6) % 360
            self.canvas.create_arc(10, 10, 50, 50, start=self._anim_angle, extent=270,
                                   outline=self.accent_color, width=4, style="arc")
        else:
            self.canvas.create_oval(22, 22, 38, 38, outline=self.accent_color, width=2)
        self.after(30, self.animate)

    # ------------------------------------------------------------------
    # CHAT
    # ------------------------------------------------------------------
    def new_chat(self):
        self.current_chat_id = str(datetime.datetime.now().timestamp())
        self.chat_history[self.current_chat_id] = []
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0","end")
        self.chat_display.configure(state="disabled")
        self._clear_variants()
        self.update_sidebar_list()

    def load_chat(self, cid):
        self.current_chat_id = cid
        self._clear_variants()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0","end")
        for e in self.chat_history[cid]:
            prefix = "👤 Du" if e.get("sender") == "Du" else "✦ Nova"
            self.chat_display.insert("end", f"{prefix}\n{e.get('msg','')}\n\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def append_chat(self, sender, msg):
        self.chat_history[self.current_chat_id].append({"sender": sender, "msg": msg})
        self._save_json(self.chat_history, HISTORY_FILE)
        self.chat_display.configure(state="normal")
        prefix = "👤 Du" if sender == "Du" else "✦ Nova"
        self.chat_display.insert("end", f"{prefix}\n{msg}\n\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")
        if len(self.chat_history[self.current_chat_id]) == 1:
            self.update_sidebar_list()

    def send_message(self):
        if self.is_thinking: return
        u = self.entry.get().strip()
        if not u: return
        self._clear_variants()
        self.append_chat("Du", u)
        self.entry.delete(0,"end")
        self.is_thinking = True
        threading.Thread(target=self.logic, args=(u,), daemon=True).start()

    def logic(self, user_input):
        try:
            persona  = self.settings.get("personality","🤖 Standard")
            system   = PERSONALITIES.get(persona, PERSONALITIES["🤖 Standard"])
            provider = self.settings.get("provider","Groq")
            model    = self.settings.get("model","llama3-70b-8192")

            pref = self.learning.get("preferred",{})
            if pref:
                top   = sorted(pref.items(), key=lambda x: -x[1])[:2]
                hints = ", ".join([k for k,_ in top])
                system += f"\n\nDer Nutzer bevorzugt Antworten die: {hints}."

            all_msgs = self.chat_history[self.current_chat_id]
            hist = [
                {'role':'user' if m['sender']=='Du' else 'assistant','content':m['msg']}
                for m in all_msgs[:-1][-10:]
            ]

            use_multi = self.settings.get("multi_answer",True)

            if use_multi and random.random() < 0.4:
                variants = []
                for style in ["kurz und direkt","ausführlicher und erklärend"]:
                    sys_v = system + f"\n\nAntworte jetzt {style}."
                    msgs  = [{'role':'system','content':sys_v},*hist,
                             {'role':'user','content':user_input}]
                    variants.append(ask_model(msgs, provider, model))
                self.is_thinking = False
                self.after(0, lambda v=variants: self._show_variants(v))
            else:
                msgs = [{'role':'system','content':system},*hist,
                        {'role':'user','content':user_input}]
                res  = ask_model(msgs, provider, model)
                self.is_thinking = False
                self.after(0, lambda: self.append_chat("Nova", res))

        except Exception as e:
            self.is_thinking = False
            err = f"⚠️ Fehler: {e}"
            self.after(0, lambda: self.append_chat("Nova", err))

    # ------------------------------------------------------------------
    # VARIANTEN
    # ------------------------------------------------------------------
    def _show_variants(self, variants):
        self._pending_variants = variants
        self._clear_variants()
        label = ctk.CTkLabel(self.variants_frame,
                             text="✦ Welche Antwort gefällt dir besser?",
                             font=("Arial",13,"bold"))
        label.pack(pady=(6,4))
        self._variant_buttons.append(label)
        for i, v in enumerate(variants):
            preview = v[:80].replace("\n"," ") + ("…" if len(v)>80 else "")
            btn = ctk.CTkButton(self.variants_frame,
                                text=f"{'⚡ Kurz' if i==0 else '📖 Ausführlich'}: {preview}",
                                fg_color=self.accent_color, hover_color=self.hover_color,
                                anchor="w", wraplength=700, justify="left",
                                command=lambda idx=i: self._pick_variant(idx))
            btn.pack(fill="x", padx=10, pady=3)
            self._variant_buttons.append(btn)

    def _pick_variant(self, idx):
        if not self._pending_variants: return
        chosen = self._pending_variants[idx]
        style  = "kurz und direkt" if idx==0 else "ausführlicher und erklärend"
        pref   = self.learning.setdefault("preferred",{})
        pref[style] = pref.get(style,0)+1
        self._save_json(self.learning, LEARNING_FILE)
        self._clear_variants()
        self.append_chat("Nova", chosen)

    def _clear_variants(self):
        for w in self._variant_buttons:
            try: w.destroy()
            except: pass
        self._variant_buttons  = []
        self._pending_variants = []

    # ------------------------------------------------------------------
    # SIDEBAR
    # ------------------------------------------------------------------
    def update_sidebar_list(self):
        for w in self.history_frame.winfo_children(): w.destroy()
        query = self.search_entry.get().lower() if hasattr(self,"search_entry") else ""
        for cid in reversed(list(self.chat_history.keys())):
            msgs  = self.chat_history[cid]
            first = msgs[0].get("msg","Neuer Chat") if msgs else "Neuer Chat"
            if query and not any(query in m.get("msg","").lower() for m in msgs): continue
            title = (first[:15]+"…") if len(first)>15 else first
            frame = ctk.CTkFrame(self.history_frame, fg_color="transparent")
            frame.pack(fill="x", pady=2)
            ctk.CTkButton(frame, text=title, fg_color="transparent", anchor="w",
                          width=150, command=lambda x=cid: self.load_chat(x)).pack(side="left",fill="x",expand=True)
            ctk.CTkButton(frame, text="❌", width=30, fg_color="#444",
                          command=lambda x=cid: self.delete_chat(x)).pack(side="right")

    def delete_chat(self, cid):
        if cid in self.chat_history:
            del self.chat_history[cid]
            self._save_json(self.chat_history, HISTORY_FILE)
            if self.current_chat_id == cid: self.new_chat()
            self.update_sidebar_list()

    # ------------------------------------------------------------------
    # AKTIONEN
    # ------------------------------------------------------------------
    def copy_last_answer(self):
        msgs = self.chat_history.get(self.current_chat_id,[])
        for m in reversed(msgs):
            if m.get("sender") == "Nova":
                self.clipboard_clear()
                self.clipboard_append(m.get("msg",""))
                self.copy_btn.configure(text="✅ Kopiert!")
                self.after(2000, lambda: self.copy_btn.configure(text="📋 Letzte Antwort kopieren"))
                return

    def export_chat(self):
        msgs = self.chat_history.get(self.current_chat_id,[])
        if not msgs:
            self._show_status("Kein Chat zum Exportieren.")
            return
        ts   = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        path = os.path.join(os.path.expanduser("~/Desktop"), f"Nova_Chat_{ts}.txt")
        with open(path,"w",encoding="utf-8") as f:
            f.write(f"Nova AI Chat – {ts}\n{'='*50}\n\n")
            for m in msgs:
                f.write(f"[{'Du' if m.get('sender')=='Du' else 'Nova'}]\n{m.get('msg','')}\n\n")
        self._show_status(f"Exportiert: {path}")

    def clear_all_history(self):
        self.chat_history = {}
        self._save_json(self.chat_history, HISTORY_FILE)
        self.new_chat()

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------
    def _load_json(self, f):
        if os.path.exists(f):
            try:
                with open(f,"r",encoding="utf-8") as file: return json.load(file)
            except: pass
        return None

    def _save_json(self, data, f):
        with open(f,"w",encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    app = NovaApp()
    app.mainloop()
