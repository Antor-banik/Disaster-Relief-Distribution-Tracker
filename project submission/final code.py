import os, sqlite3, csv, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "drdt.db")

# Optional hero image (PNG/GIF). If not found, a vector illustration will be used.
HERO_IMAGE_PATH = os.path.join(BASE_DIR, "hero.png")


BG        = "#f4f6f8"
CARD      = "#ffffff"
TOP       = "#0ea5a3"   # teal
TOP_DARK  = "#0b8685"
ACCENT    = "#ff6b57"   # soft orange
TXT_DARK  = "#1f2937"
MUTED     = "#6b7280"
STRIPE_E  = "#f8fafc"
STRIPE_O  = "#ffffff"

FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_HERO  = ("Segoe UI", 28, "bold")
FONT_SUB   = ("Segoe UI", 12, "bold")
FONT       = ("Segoe UI", 10)


def get_conn(): return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as con:
        cur = con.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS people(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, area TEXT NOT NULL, age INTEGER
        );
        CREATE TABLE IF NOT EXISTS aid_types(
            id INTEGER PRIMARY KEY AUTOINCREMENT, aid_name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS aid_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL, aid_type TEXT NOT NULL, request_date TEXT NOT NULL,
            FOREIGN KEY(person_id) REFERENCES people(id)
        );
        CREATE TABLE IF NOT EXISTS aid_delivered(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL, item_given TEXT NOT NULL, delivery_date TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES aid_requests(id)
        );
        """)
        cur.executemany("INSERT OR IGNORE INTO aid_types(aid_name) VALUES(?)",
                        [("Food",), ("Medicine",), ("Shelter",), ("Clothing",), ("Water",)])
        con.commit()

def add_person(name, area, age):
    with get_conn() as con:
        con.execute("INSERT INTO people(name,area,age) VALUES (?,?,?)",
                    (name, area, age if age else None))

def list_people():
    with get_conn() as con:
        return list(con.execute("SELECT id,name,area,COALESCE(age,'') FROM people ORDER BY id DESC"))

def list_aid_types():
    with get_conn() as con:
        return [r[0] for r in con.execute("SELECT aid_name FROM aid_types ORDER BY aid_name")]

def add_request(pid, aid_type, req_date):
    with get_conn() as con:
        con.execute("INSERT INTO aid_requests(person_id,aid_type,request_date) VALUES (?,?,?)",
                    (pid, aid_type, req_date))

def list_pending_requests():
    q = """SELECT r.id,p.name,p.area,r.aid_type,r.request_date
           FROM aid_requests r JOIN people p ON p.id=r.person_id
           LEFT JOIN aid_delivered d ON d.request_id=r.id
           WHERE d.id IS NULL ORDER BY r.id DESC"""
    with get_conn() as con: return list(con.execute(q))

def mark_delivered(rid, item, d_date):
    with get_conn() as con:
        con.execute("INSERT INTO aid_delivered(request_id,item_given,delivery_date) VALUES (?,?,?)",
                    (rid, item, d_date))

def search(area="", status="All"):
    q = """SELECT p.name,p.area,r.aid_type,r.request_date,
           CASE WHEN d.id IS NULL THEN 'PENDING' ELSE d.delivery_date END
           FROM aid_requests r JOIN people p ON p.id=r.person_id
           LEFT JOIN aid_delivered d ON d.request_id=r.id"""
    w, prm = [], []
    if area: w.append("p.area LIKE ?"); prm.append(f"%{area}%")
    if status=="Pending": w.append("d.id IS NULL")
    elif status=="Delivered": w.append("d.id IS NOT NULL")
    if w: q += " WHERE " + " AND ".join(w)
    q += " ORDER BY r.id DESC"
    with get_conn() as con: return list(con.execute(q, prm))

def delivered_summary_by_area():
    q = """SELECT p.area,COUNT(*) FROM aid_delivered d
           JOIN aid_requests r ON r.id=d.request_id
           JOIN people p ON p.id=r.person_id
           GROUP BY p.area ORDER BY COUNT(*) DESC"""
    with get_conn() as con: return list(con.execute(q))

def export_to_csv(data, filename):
    with open(filename,'w',newline='',encoding='utf-8') as f: csv.writer(f).writerows(data)

def make_entry(parent, label, width=20, row=0, col=0, **kw):
    tk.Label(parent,text=label,bg=CARD,fg=TXT_DARK,font=FONT).grid(row=row,column=col,padx=8,sticky="w")
    var=tk.StringVar(); e=ttk.Entry(parent,textvariable=var,font=FONT,width=width,**kw)
    e.grid(row=row,column=col+1,padx=8); return var

def make_combo(parent, label, values, width=20, row=0, col=0):
    tk.Label(parent,text=label,bg=CARD,fg=TXT_DARK,font=FONT).grid(row=row,column=col,padx=8,sticky="w")
    var=tk.StringVar(); cb=ttk.Combobox(parent,textvariable=var,font=FONT,width=width,state="readonly",values=values)
    cb.grid(row=row,column=col+1,padx=8); return var,cb

def make_treeview(parent, cols, widths):
    frame=tk.Frame(parent,bg=CARD); frame.pack(fill="both",expand=True)
    tree=ttk.Treeview(frame,columns=cols,show="headings",height=12)
    for c,w in zip(cols,widths):
        tree.heading(c,text=c)
        tree.column(c,width=w,anchor="center" if c in ("ID","Age","Deliveries","Status") else "w")
    sb=ttk.Scrollbar(frame,orient="vertical",command=tree.yview); tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
    tree.tag_configure('even',background=STRIPE_E); tree.tag_configure('odd',background=STRIPE_O)
    return tree

def refresh_tree(tree, rows):
    tree.delete(*tree.get_children())
    for i,r in enumerate(rows):
        tree.insert("", "end", values=r, tags=('even' if i%2==0 else 'odd',))

class DRDTApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Disaster Relief Distribution Tracker")
        self.geometry("1150x720")
        self.minsize(1050, 680)
        self.configure(bg=BG)

        header = tk.Frame(self, bg=TOP, height=64)
        header.pack(fill="x", side="top")

      
        logo = tk.Canvas(header, width=44, height=44, bg=TOP, highlightthickness=0)
        logo.pack(side="left", padx=14, pady=10)
        logo.create_oval(2,2,42,42, fill="white", outline="")
     
        logo.create_rectangle(20-3,10,20+3,34, fill=TOP, outline="")
        logo.create_rectangle(10,20-3,34,20+3, fill=TOP, outline="")

        tk.Label(header, text="ReliefTrack", font=("Segoe UI", 16, "bold"),
                 bg=TOP, fg="white").pack(side="left")

        nav = tk.Frame(header, bg=TOP)
        nav.pack(side="right", padx=12)
        self.nav_btns = {}
        def navbtn(title, idx):
            b = tk.Button(nav, text=title, font=("Segoe UI",10,"bold"),
                          fg="white", bg=TOP, bd=0, activebackground=TOP_DARK,
                          cursor="hand2",
                          command=lambda: self.nb.select(idx))
            b.pack(side="left", padx=8, pady=14)
            self.nav_btns[title]=b

       
        card = tk.Frame(self, bg=BG)
        card.pack(fill="both", expand=True, padx=18, pady=18)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[14, 6], font=FONT_SUB)
        style.map("TNotebook.Tab", background=[("selected", CARD), ("active", "#e9eef2")])

        self.nb = ttk.Notebook(card)
        self.nb.pack(fill="both", expand=True)

       
        self.home    = HomeTab(self.nb, on_manage=lambda: self.nb.select(1), on_reports=lambda: self.nb.select(5))
        self.people  = PeopleTab(self.nb)
        self.request = RequestTab(self.nb)
        self.deliver = DeliverTab(self.nb)
        self.search  = SearchTab(self.nb)
        self.reports = ReportsTab(self.nb)

        for t, name in [
            (self.home,   " Home "),
            (self.people, " People "),
            (self.request," Aid Request "),
            (self.deliver," Deliver Aid "),
            (self.search, " Search/Filter "),
            (self.reports," Reports "),
        ]: self.nb.add(t, text=name)

        
        for i, title in enumerate(["Home","People","Requests","Deliver","Search","Reports"]):
            navbtn(title, i)

      
        self.request.refresh_people()
        self.deliver.refresh()
        self.search.refresh()
        self.reports.refresh()

class HomeTab(ttk.Frame):
    def __init__(self, parent, on_manage, on_reports):
        super().__init__(parent, padding=0)
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True)

        # Hero card
        hero = tk.Frame(root, bg=CARD, bd=0, relief="flat")
        hero.pack(fill="both", expand=False, padx=28, pady=28)

       
        left  = tk.Frame(hero, bg=CARD)
        right = tk.Frame(hero, bg=CARD)
        left.pack(side="left", fill="both", expand=True, padx=18, pady=18)
        right.pack(side="right", fill="both", expand=False, padx=18, pady=18)

        tk.Label(left, text="COORDINATE • RESPOND • RELIEVE",
                 bg=CARD, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4,6))

        tk.Label(left, text="Disaster Relief\nDistribution Tracker",
                 bg=CARD, fg=TXT_DARK, font=FONT_HERO, justify="left").pack(anchor="w")

        tk.Label(left, text="Track people in need, log aid requests, and record deliveries\nin one clean dashboard.",
                 bg=CARD, fg=MUTED, font=FONT).pack(anchor="w", pady=(8,16))

      
        ctas = tk.Frame(left, bg=CARD)
        ctas.pack(anchor="w", pady=(6, 18))
        tk.Button(ctas, text="Manage Data", command=on_manage,
                  font=("Segoe UI",10,"bold"), fg="white", bg=ACCENT,
                  activebackground="#e85a47", bd=0, padx=16, pady=10, cursor="hand2").pack(side="left")
        tk.Button(ctas, text="View Reports", command=on_reports,
                  font=("Segoe UI",10,"bold"), fg=TOP, bg="#e6fffd",
                  activebackground="#d9fffb", bd=0, padx=16, pady=10, cursor="hand2").pack(side="left", padx=10)

    
        canvas = tk.Canvas(right, width=420, height=260, bg=CARD, highlightthickness=0)
        canvas.pack()
        if os.path.exists(HERO_IMAGE_PATH):
            try:
                self.hero_img = tk.PhotoImage(file=HERO_IMAGE_PATH)
                # auto fit (simple center)
                iw, ih = self.hero_img.width(), self.hero_img.height()
                ratio = min(420/iw, 260/ih)
                # PhotoImage has no smooth resize; just center display
                canvas.create_image(210, 130, image=self.hero_img)
            except Exception:
                self._draw_vector(canvas)
        else:
            self._draw_vector(canvas)

       
        stat = tk.Frame(root, bg=BG)
        stat.pack(fill="x", padx=28)
        for text in ["Register People", "Add Aid Requests", "Deliver & Verify", "Export Reports"]:
            badge = tk.Frame(stat, bg="#eef7f7", padx=12, pady=8)
            badge.pack(side="left", padx=8, pady=10)
            tk.Label(badge, text=text, bg="#eef7f7", fg=TOP_DARK, font=("Segoe UI", 9, "bold")).pack()

    def _draw_vector(self, c: tk.Canvas):
        
        c.create_oval(-200,180,620,380, fill="#f0fbfb", outline="")
        c.create_oval(-220,140,600,340, fill="#e6fffd", outline="")
       
        c.create_rectangle(160,70,260,190, fill="#d1faf9", outline="")
        c.create_rectangle(175,145,245,175, fill="#ffffff", outline="")
        c.create_oval(185,40,235,90, fill="#c7e4ff", outline="")
        c.create_rectangle(190,90,230,120, fill="#bfe3ff", outline="")

class PeopleTab(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent, padding=15)
        form=tk.Frame(self,bg=CARD); form.pack(fill="x",pady=10)
        self.name=make_entry(form,"Name:",25,0,0)
        self.area=make_entry(form,"Area:",25,0,2)
        self.age =make_entry(form,"Age:",10,0,4)
        ttk.Button(form,text="Add Person",command=self.on_add).grid(row=0,column=6,padx=10)
        self.tree=make_treeview(self,("ID","Name","Area","Age"),(60,220,220,80)); self.refresh()

    def on_add(self):
        if not self.name.get() or not self.area.get():
            return messagebox.showerror("Error","Name & Area required")
        if self.age.get() and not self.age.get().isdigit():
            return messagebox.showerror("Error","Age must be number")
        add_person(self.name.get(),self.area.get(),int(self.age.get()) if self.age.get() else None)
        self.name.set(""); self.area.set(""); self.age.set("")
        self.refresh(); app.request.refresh_people(); app.deliver.refresh(); app.search.refresh(); app.reports.refresh()

    def refresh(self): refresh_tree(self.tree, list_people())

class RequestTab(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent, padding=15)
        form=tk.Frame(self,bg=CARD); form.pack(fill="x",pady=10)
        self.person_var,self.cb_person=make_combo(form,"Person:",[],28,0,0)
        self.aid_var,   self.cb_aid   =make_combo(form,"Aid Type:",list_aid_types(),20,0,2)
        self.date=tk.StringVar(value=str(date.today()))
        ttk.Entry(form,textvariable=self.date,width=12,state="readonly").grid(row=0,column=5)
        ttk.Button(form,text="Add Request",command=self.on_add).grid(row=0,column=6,padx=10)
        self.tree=make_treeview(self,("ID","Name","Area","Aid Type","Request Date"),(60,220,180,160,140))

    def refresh_people(self):
        people=list_people()
        self.cb_person['values']=[f"{p[0]} - {p[1]} ({p[2]})" for p in people]
        if people: self.cb_person.current(0)

    def on_add(self):
        if not self.person_var.get() or not self.aid_var.get():
            return messagebox.showerror("Error","Select person & aid")
        add_request(self.person_var.get().split(" - ")[0], self.aid_var.get(), self.date.get())
        self.aid_var.set("")
        self.refresh(); app.deliver.refresh(); app.search.refresh(); app.reports.refresh()
        messagebox.showinfo("Success","Aid request added")

    def refresh(self): refresh_tree(self.tree, list_pending_requests())

class DeliverTab(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent, padding=15)
        form=tk.Frame(self,bg=CARD); form.pack(fill="x",pady=10)
        self.req_var,self.cb_req = make_combo(form,"Request:",[],30,0,0)
        self.items  = make_entry(form,"Items:",25,0,2)
        self.d_date = make_entry(form,"Delivery Date:",12,0,4); self.d_date.set(str(date.today()))
        ttk.Button(form,text="Mark Delivered",command=self.on_deliver).grid(row=0,column=6)
        self.tree=make_treeview(self,("ID","Name","Area","Aid Type","Request Date"),(60,220,180,160,140))

    def on_deliver(self):
        if not self.req_var.get() or not self.items.get():
            return messagebox.showerror("Error","Fill all fields")
        mark_delivered(self.req_var.get().split(" - ")[0], self.items.get(), self.d_date.get())
        self.items.set(""); self.req_var.set("")
        self.refresh(); app.request.refresh(); app.search.refresh(); app.reports.refresh()
        messagebox.showinfo("Success","Aid delivery recorded")

    def refresh(self):
        rows=list_pending_requests(); refresh_tree(self.tree, rows)
        self.cb_req['values']=[f"{r[0]} - {r[1]}" for r in rows]

class SearchTab(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent, padding=15)
        form=tk.Frame(self,bg=CARD); form.pack(fill="x",pady=10)
        self.area=make_entry(form,"Area:",25,0,0)
        self.status,self.cb_status=make_combo(form,"Status:",["All","Pending","Delivered"],15,0,2); self.status.set("All")
        ttk.Button(form,text="Search",command=self.refresh).grid(row=0,column=4,padx=6)
        ttk.Button(form,text="Export CSV",command=self.on_export).grid(row=0,column=5)
        self.tree=make_treeview(self,("Name","Area","Aid Type","Request Date","Status"),(220,180,160,140,120))
        self.tree.tag_configure('pending',foreground="#e74c3c"); self.tree.tag_configure('delivered',foreground="#27ae60")

    def on_export(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if f:
            data=[("Name","Area","Aid Type","Request Date","Status")]
            for i in self.tree.get_children(): data.append(self.tree.item(i)['values'])
            export_to_csv(data,f); messagebox.showinfo("Success", f"Exported: {f}")

    def refresh(self):
        rows=search(self.area.get(), self.status.get())
        self.tree.delete(*self.tree.get_children())
        for i,r in enumerate(rows):
            tag = ('pending' if r[4]=='PENDING' else 'delivered')
            self.tree.insert("", "end", values=r, tags=(tag,'even' if i%2==0 else 'odd'))

class ReportsTab(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent, padding=15)
        head=tk.Frame(self,bg=CARD); head.pack(fill="x",pady=(0,10))
        tk.Label(head,text="Reports & Analytics",bg=CARD,fg=TXT_DARK,font=FONT_TITLE).pack(anchor="w",padx=6,pady=6)

       
        stats=tk.Frame(self,bg=CARD); stats.pack(fill="x",pady=6)
        self.people_v=tk.StringVar(value="0"); self.req_v=tk.StringVar(value="0")
        self.pending_v=tk.StringVar(value="0"); self.deliv_v=tk.StringVar(value="0")
        for i,(title,var) in enumerate([
            ("Total People",self.people_v),
            ("Total Requests",self.req_v),
            ("Pending Deliveries",self.pending_v),
            ("Delivered Items",self.deliv_v),
        ]): self._card(stats,title,var,i)

      
        self.tree=make_treeview(self,("Area","Deliveries"),(320,160))

    def _card(self,parent,title,var,col):
        card=tk.Frame(parent,bg="#f7fbfb",bd=1,relief="solid",padx=14,pady=10)
        card.grid(row=0,column=col, padx=8, sticky="nsew")
        tk.Label(card,text=title,bg="#f7fbfb",fg=MUTED,font=("Segoe UI",10)).pack(anchor="w")
        tk.Label(card,textvariable=var,bg="#f7fbfb",fg=TXT_DARK,font=("Segoe UI",18,"bold")).pack(anchor="w")
        parent.columnconfigure(col, weight=1)

    def refresh(self):
        self.people_v.set(len(list_people()))
        self.pending_v.set(len(list_pending_requests()))
        with get_conn() as con:
            self.req_v.set(con.execute("SELECT COUNT(*) FROM aid_requests").fetchone()[0])
            self.deliv_v.set(con.execute("SELECT COUNT(*) FROM aid_delivered").fetchone()[0])
        refresh_tree(self.tree, delivered_summary_by_area())

if __name__=="__main__":
    init_db()
    app = DRDTApp()
    app.mainloop()
