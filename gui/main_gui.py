import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys, os, json, threading, calendar
from pathlib import Path
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox


# ============= CONFIGURATION =============
from backend.email_engine import (
    read_csv_recipients, send_bulk_emails,
    schedule_email_send, get_config,
    save_config, format_email_content, save_app_state, load_app_state,
    start_background_scheduler, stop_background_scheduler,
    is_scheduler_running, check_and_execute_due_campaigns
)
ps = load_app_state()
app_state = {"csv_file":ps.get("csv_file"), "attachment_files":ps.get("attachment_files",[]), "config":get_config()}

def apply_global_style(root):
    style = ttk.Style(root)
    style.theme_use("clam")

    # ===== Global fonts =====
    style.configure(".", font=("Segoe UI", 11))

    # ===== Backgrounds =====
    style.configure("TFrame", background="#f5f7fb")
    style.configure("TLabel", background="#f5f7fb", foreground="#253142")
    style.configure("TNotebook", background="#f5f7fb")
    style.configure("TNotebook.Tab",
        padding=[14, 8],
        font=("Segoe UI", 11,)
    )

    # ===== Titles =====
    style.configure(
        "Title.TLabel",
        font=("Segoe UI", 22,),
        foreground="#1f4fd8"
    )

    style.configure(
        "Section.TLabel",
        font=("Segoe UI", 14,),
        foreground="#1f4fd8"
    )

    # ===== Buttons =====
    style.configure(
        "Accent.TButton",
        background="#1f4fd8",
        foreground="white",
        font=("Segoe UI", 11,),
        padding=10
    )

    style.map(
        "Accent.TButton",
        background=[("active", "#163db8")]
    )

    # ===== Entries =====
    style.configure("TEntry", padding=6)

def create_window():
    root = tk.Tk()
    root.title("Email Automation System")
    root.geometry("900x700")
    root.configure(bg="#f5f7fb")

    apply_global_style(root)

    return root
    

def create_notebook(root):
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    return notebook


def create_config_tab(notebook):
    frame = ttk.Frame(notebook)
    notebook.add(frame, text="⚙️ Configuration")

    # Outer container (TOP aligned, not center)
    container = ttk.Frame(frame)
    container.pack(fill=tk.BOTH, expand=True, anchor="n")

    # Card (reduced padding so content fits screen)
    card = ttk.Frame(container, padding=25)
    card.pack(pady=20)

    # ===== TITLE (BLACK, NOT BLUE) =====
    ttk.Label(
        card,
        text="SMTP Configuration",
        font=("Arial", 20, "bold"),
        foreground="black"
    ).grid(row=0, column=0, columnspan=2, pady=(0, 4))

    # ===== SUBTITLE (SMALL + GRAY) =====
    ttk.Label(
        card,
        text="Admin email settings used for sending and scheduling emails",
        font=("Segoe UI", 8),
        foreground="#6b7280"
    ).grid(row=1, column=0, columnspan=2, pady=(0, 18))

    # Fields
    fields = [
        ("Admin Email Address", "sender_email"),
        ("App Password", "sender_password"),
        ("Sender Name", "sender_name"),
        ("SMTP Server", "smtp_server"),
        ("SMTP Port", "smtp_port"),
        ("Delay (s)", "delay_between_emails"),
        ("Max Retries", "max_retries"),
    ]

    entries = {}

    for i, (label, key) in enumerate(fields, start=2):
        ttk.Label(
            card,
            text=label,
            anchor="e",
            width=26
        ).grid(row=i, column=0, sticky="e", padx=12, pady=6)

        entry = ttk.Entry(
            card,
            width=36,
            show="*" if "password" in key else ""
        )
        entry.insert(0, str(app_state["config"].get(key, "")))
        entry.grid(row=i, column=1, sticky="w", pady=6)

        entries[key] = entry

    # ===== SAVE BUTTON (NOW VISIBLE) =====
    btn_frame = ttk.Frame(card)
    btn_frame.grid(row=i + 1, column=0, columnspan=2, pady=20)

    def save_config_local():
        new_config = app_state["config"].copy()
        for key, entry in entries.items():
            val = entry.get()
            if key in ["smtp_port", "max_retries", "delay_between_emails"]:
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showerror("Invalid Input", f"{key} must be a number")
                    return
            new_config[key] = val

        save_config(new_config)
        app_state["config"] = get_config()
        messagebox.showinfo("Saved", "SMTP configuration updated successfully")
    
    ttk.Button(
    btn_frame,
    text="Save Configuration",
    style="Soft.TButton",
    command=save_config_local
).pack()
   # ===== WARNING (NOW VISIBLE) =====
    ttk.Label(
        card,
        text="⚠️ Use Google App Password (not your normal Gmail password)",
        font=("Segoe UI", 9),
        foreground="#b91c1c"
    ).grid(row=i + 2, column=0, columnspan=2, pady=(5, 0))


# ============= TAB 2: CSV MANAGEMENT =============

def create_csv_tab(notebook):
    frame = ttk.Frame(notebook, padding=10)
    notebook.add(frame, text="📄 CSV File")
    ttk.Label(frame, text="CSV File Management", font=("Arial", 18, "bold")).pack(pady=(10,5))
    
    lbl_txt = f"Selected: {Path(app_state['csv_file']).name}" if app_state["csv_file"] and os.path.exists(app_state["csv_file"]) else "No file selected"
    file_label = ttk.Label(frame, text=lbl_txt, foreground="blue", font=("Arial", 10))
    file_label.pack(pady=(0,5))
    
    # File button
    def select_csv():
        fname = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if fname:
            app_state["csv_file"] = fname
            file_label.config(text=f"Selected: {Path(fname).name}")
            save_app_state({"csv_file": fname, "attachment_files": app_state["attachment_files"], "last_updated": datetime.now().isoformat()})
    
    ttk.Button(frame, text="Select CSV File", command=select_csv).pack(pady=10)
    ttk.Label(frame, text="CSV Preview:", font=("Segoe UI", 15, "bold")).pack(pady=(20, 5))
    preview_container = ttk.Frame(frame)
    preview_container.pack(pady=(0,10))

    preview_text = scrolledtext.ScrolledText(preview_container, width=100, height=15, font=("Consolas", 10))
    preview_text.pack(pady=10, fill=tk.BOTH, expand=True)
    
    def show_preview():
        if not app_state["csv_file"]: messagebox.showwarning("Warning", "Select a CSV file first"); return
        try:
            recs = read_csv_recipients(app_state["csv_file"])
            preview_text.config(state=tk.NORMAL)
            preview_text.delete(1.0, tk.END)
            preview_text.insert(tk.END, f"Total Recipients: {len(recs)}\n{'='*70}\n\n")
            for i, r in enumerate(recs[:10], 1):
                preview_text.insert(tk.END, f"{i}. Name: {r.get('name','N/A')}\n   Email: {r.get('email','N/A')}\n\n")
            if len(recs) > 10: preview_text.insert(tk.END, f"... and {len(recs)-10} more\n")
            preview_text.config(state=tk.DISABLED)
        except Exception as e: messagebox.showerror("Error", str(e))
    ttk.Button(frame, text="Show Preview", command=show_preview).pack(pady=(5,10))

#Attachment tab

def create_attachment_tab(notebook):
    frame = ttk.Frame(notebook, padding=20)
    notebook.add(frame, text="📎 Attachments")
    
    ttk.Label(frame, text="Attachments", font=("Segoe UI", 20, "bold")).pack(pady=12)
    listbox_container = ttk.Frame(frame)
    listbox_container.pack(pady=10)

    # Smaller, centered listbox
    listbox = tk.Listbox(
    listbox_container,
    height=15,
    width=100,  # smaller than before
    font=("Consolas", 11)
)
    listbox.pack(padx=20, pady=5)
    def save():
        save_app_state({
            "csv_file": app_state["csv_file"],
            "attachment_files": app_state["attachment_files"],
            "last_updated": datetime.now().isoformat()
        })
        
    def upd():
        listbox.delete(0, tk.END)
        for f in app_state["attachment_files"]:
            listbox.insert(tk.END, Path(f).name)
            
    def add():
        fs = filedialog.askopenfilenames()
        if fs:
            for f in fs:
                if f not in app_state["attachment_files"]:
                    app_state["attachment_files"].append(f)
            upd()
            save()
            
    def rem():
        if listbox.curselection():
            app_state["attachment_files"].pop(listbox.curselection()[0])
            upd()
            save()
            
    def clr():
        app_state["attachment_files"].clear()
        upd()
        save()
        
    def load():
        app_state.update({"attachment_files": [f for f in app_state["attachment_files"] if os.path.exists(f)]})
        upd()
        
    frame.after(100, load)
    
    bf = ttk.Frame(frame)
    bf.pack(pady=12)
    ttk.Button(bf, text="Add", command=add,style="Soft.TButton").pack(side=tk.LEFT, padx=2)
    ttk.Button(bf, text="Remove", command=rem,style="Soft.TButton").pack(side=tk.LEFT, padx=2)
    ttk.Button(bf, text="Clear", command=clr,style="Soft.TButton").pack(side=tk.LEFT, padx=2)

#template tab
def create_template_tab(notebook):
    frame = ttk.Frame(notebook, padding=20)
    notebook.add(frame, text="✉️ Templates")
    
    # Outer container to center content
    container = ttk.Frame(frame)
    container.pack(expand=True, fill=tk.BOTH)

    # Card frame for centering
    card = ttk.Frame(container, padding=15)
    card.pack(pady=10,)

    # Title
    ttk.Label(card, text="Template Editor", font=("Arial", 16, "bold")).pack(pady=(0, 10))

    # Subject Entry
    sub = ttk.Entry(card, width=60, font=("Segoe UI", 11))  # narrower width
    sub.insert(0, "Hello {name}")
    sub.pack(pady=(0, 5), fill=tk.X)

    # Body Text
    body = scrolledtext.ScrolledText(card, width=100, height=14, font=("Segoe UI", 11))  # match width
    body.insert(tk.END, "Dear {name},\n\n{custom_message}\n\nBest, System")
    body.pack(pady=(0, 5), fill=tk.BOTH, expand=True)

    # Placeholders label
    ttk.Label(
        card,
        text="Placeholders: {name}, {custom_message}",
        foreground="gray",
        font=("Arial", 9)
    ).pack(pady=(0, 5))

    return sub, body


#send emails tab
def create_test_send_tab(notebook, sub_e, body_t):
    frame = ttk.Frame(notebook, padding=20)
    notebook.add(frame, text="🚀 Send")
    
    # Outer container to center content
    container = ttk.Frame(frame)
    container.pack(expand=True)

    # Card frame
    card = ttk.Frame(container, padding=20)
    card.pack(pady=30)

    # Title
    ttk.Label(card, text="Send Emails", font=("Arial", 16, "bold")).pack(pady=(0, 10))

    # Options frame
    opt_f = ttk.LabelFrame(card, text="Options", padding=10)
    opt_f.pack(pady=10, fill=tk.X)

    html_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(opt_f, text="HTML", variable=html_var).pack(anchor=tk.W)

    # Status label
    stat_lbl = ttk.Label(card, text="READY!", foreground="blue", font=("Segoe UI", 13, "bold"))
    stat_lbl.pack(pady=5)

    # Output box (log)
    out = scrolledtext.ScrolledText(card, width=100, height=12, font=("Consolas", 11), state=tk.DISABLED)
    out.pack(pady=10, fill=tk.BOTH, expand=True)

    def log(m):
        out.config(state=tk.NORMAL)
        out.insert(tk.END, m + "\n")
        out.see(tk.END)
        out.config(state=tk.DISABLED)

    # Send button
    def run_send():
        if not app_state["csv_file"]:
            messagebox.showwarning("Warning", "Select CSV")
            return
        stat_lbl.config(text="SENDING...", foreground="orange")
        def run():
            try:
                res = send_bulk_emails(
                    app_state["csv_file"],
                    body_t.get(1.0, tk.END),
                    sub_e.get(),
                    app_state["attachment_files"],
                    html_var.get()
                )
                log(f"Sent: {res['sent']}, Failed: {res['failed']}")
                stat_lbl.config(text="DONE!", foreground="green")
            except Exception as e:
                log(f"Error: {e}")
                stat_lbl.config(text="ERROR!", foreground="red")
        threading.Thread(target=run, daemon=True).start()

    ttk.Button(card, text="Send Emails", command=run_send, style="Soft.TButton").pack(pady=10)

#Scheduale tab
def create_calendar_popup(parent, callback):
    pop = tk.Toplevel(parent)
    pop.title("Date")
    pop.geometry("300x320")
    pop.grab_set()
    
    y_v = tk.IntVar(value=datetime.now().year)
    m_v = tk.IntVar(value=datetime.now().month)
    hdr = ttk.Frame(pop)
    hdr.pack(pady=5)
    
    def chg(d):
        m = m_v.get() + d
        if m == 0:
            m_v.set(12)
            y_v.set(y_v.get() - 1)
        elif m == 13:
            m_v.set(1)
            y_v.set(y_v.get() + 1)
        else:
            m_v.set(m)
        upd()
        
    ttk.Button(hdr, text="<", width=2, command=lambda: chg(-1)).pack(side=tk.LEFT)
    m_l = ttk.Label(hdr, text="", font=("Arial", 10, "bold"))
    m_l.pack(side=tk.LEFT, padx=10)
    ttk.Button(hdr, text=">", width=2, command=lambda: chg(1)).pack(side=tk.LEFT)
    
    cal_f = ttk.Frame(pop)
    cal_f.pack()
    for i, d in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
        ttk.Label(cal_f, text=d).grid(row=0, column=i)
        
    btns = []
    def upd():
        for b in btns: b.destroy()
        btns.clear()
        y, m = y_v.get(), m_v.get()
        m_l.config(text=f"{calendar.month_name[m]} {y}")
        for r, w in enumerate(calendar.Calendar(0).monthdayscalendar(y, m)):
            for c, d in enumerate(w):
                if d == 0: continue
                b = tk.Button(cal_f, text=str(d), command=lambda d=d: (callback(f"{y}-{m:02d}-{d:02d}"), pop.destroy()))
                if datetime(y, m, d).date() < datetime.now().date():
                    b.config(state=tk.DISABLED)
                b.grid(row=r+1, column=c)
                btns.append(b)
                
    upd()
    ttk.Button(pop, text="Cancel", command=pop.destroy).pack(pady=5)


def create_time_picker_popup(parent, callback):
    pop = tk.Toplevel(parent)
    pop.title("Time")
    pop.geometry("300x200")
    pop.grab_set()
    
    h_v = tk.IntVar(value=10)
    m_v = tk.IntVar(value=0)
    a_v = tk.StringVar(value="AM")
    f = ttk.Frame(pop)
    f.pack(pady=10)
    
    for v, mx in [(h_v, 12), (m_v, 59)]:
        cf = ttk.Frame(f)
        cf.pack(side=tk.LEFT, padx=5)
        ttk.Button(cf, text="^", width=2, command=lambda v=v, mx=mx: v.set(1 if v.get() >= mx else v.get() + 1)).pack()
        tk.Label(cf, textvariable=v, font=("Arial", 18)).pack()
        ttk.Button(cf, text="v", width=2, command=lambda v=v, mx=mx: v.set(mx if v.get() <= 1 else v.get() - 1)).pack()
        
    ttk.Button(f, text="AM", command=lambda: a_v.set("AM")).pack(side=tk.LEFT, padx=5)
    ttk.Button(f, text="PM", command=lambda: a_v.set("PM")).pack(side=tk.LEFT, padx=5)
    
    def save():
        h = h_v.get()
        if a_v.get() == "PM" and h != 12: h += 12
        elif a_v.get() == "AM" and h == 12: h = 0
        callback(f"{h:02d}:{m_v.get():02d}", f"{h_v.get()}:{m_v.get():02d} {a_v.get()}")
        pop.destroy()
        
    ttk.Button(pop, text="OK", command=save).pack(pady=10)

def create_schedule_tab(notebook, sub_e, body_t):
    f = ttk.Frame(notebook, padding=20)
    notebook.add(f, text="📅 Schedule")
    t_24h = tk.StringVar(value="10:00")
    
    # Date & Time frame
    ir = ttk.Frame(f)
    ir.pack(pady=10)
    
    # Date entry
    de = ttk.Entry(ir, width=15)
    de.insert(0, (datetime.now() + timedelta(1)).strftime("%Y-%m-%d"))
    de.pack(side=tk.LEFT)
    ttk.Button(ir, text="Date", command=lambda: create_calendar_popup(f, lambda d: (de.delete(0, tk.END), de.insert(0, d)))).pack(side=tk.LEFT)
    
    # Time entry
    te = ttk.Entry(ir, width=15)
    te.insert(0, "10:00 AM")
    te.pack(side=tk.LEFT)
    ttk.Button(ir, text="Time", command=lambda: create_time_picker_popup(f, lambda t24, td: (t_24h.set(t24), te.delete(0, tk.END), te.insert(0, td)))).pack(side=tk.LEFT)
    
    # History / status box
    out = scrolledtext.ScrolledText(f, height=10, width=50, font=("Consolas", 10))
    out.pack(fill=tk.BOTH, expand=True)

    # Button callbacks
    def schedule_email():
        if not app_state["csv_file"]:
            messagebox.showwarning("Warning", "Please select a CSV file first")
            return
        
        date = de.get()
        time = t_24h.get()
        subject = sub_e.get()
        body = body_t.get("1.0", tk.END).strip()
        
        if not date or not time or not subject or not body:
            messagebox.showwarning("Warning", "Please fill in all fields (date, time, subject, body)")
            return
        
        # Call the actual scheduling function
        result = schedule_email_send(
            csv_file=app_state["csv_file"],
            email_template=body,
            subject_template=subject,
            send_date=date,
            send_time=time,
            attachment_paths=app_state["attachment_files"],
            is_html=False
        )
        
        if result["is_scheduled"]:
            out.insert(tk.END, f"✓ {result['message']}\n")
            messagebox.showinfo("Success", result['message'])
        else:
            out.insert(tk.END, f"✗ {result['message']}\n")
            messagebox.showerror("Error", result['message'])
        
        out.see(tk.END)

    
    def clear_history():
        out.delete("1.0", tk.END)


    # Buttons frame
    btn_frame = ttk.Frame(f)
    btn_frame.pack(pady=15)

    ttk.Button(btn_frame, text="Schedule Email", command=schedule_email).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text="Clear", command=clear_history,).pack(side=tk.LEFT, padx=5)


def main():
    root = create_window()
    header = tk.Frame(root, bg="#72a0b8", height=80)
    header.pack(fill=tk.X)

    header.pack_propagate(False)

    title = tk.Label(
        header,
        text="📧 Email Automation System",
        bg="#72a0b8",
        fg="#FBFCFD",
        font=("Segoe UI", 24, "bold")
    )
    title.place(relx=0.5, rely=0.5, anchor="center")
    nb = create_notebook(root)
    create_config_tab(nb)
    create_csv_tab(nb)
    create_attachment_tab(nb)
    sub, body = create_template_tab(nb)
    create_test_send_tab(nb, sub, body)
    create_schedule_tab(nb, sub, body)
    
    # Start background scheduler BEFORE mainloop
    def on_exec(cid, res):
        root.after(100, lambda: messagebox.showinfo("Executed", f"Campaign {cid} successfully sent!"))
    
    start_background_scheduler(30, on_exec)
    root.after(2000, lambda: check_and_execute_due_campaigns(on_exec))
    
    def end():
        stop_background_scheduler()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", end)
    root.mainloop()

if __name__ == "__main__":
    main()


