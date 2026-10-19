"""Accessible Tk desktop controls: each configuration step has an explicit button."""
from __future__ import annotations
from datetime import datetime, timezone
from queue import Queue, Empty
from threading import Thread
import time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from .core import AlertEngine, ReadingError, decode_reading
from .homeassistant import HomeAssistant, HomeAssistantError
from .outputs import beep, start_speech
from .settings import Settings, save_token, load_token
from .contacts import ContactRoute, read_routes, emergency_message, dispatch_emergency
from .readiness import setup_checks
from .health import ConnectionHealth
from .delivery import DeliveryTracker
from . import __version__

HELP_URL = 'https://support.microsoft.com/en-gb/windows/apps/phonelink/setting-up-notifications-in-the-phone-link'

class LibreBeaconApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f'LibreBeacon {__version__} — Accessibility Companion (experimental)')
        root.minsize(920, 710)
        try:
            self.settings = Settings.load()
        except (OSError, ValueError, TypeError):
            self.settings = Settings()
        self.session_token = load_token()
        self.engine = AlertEngine()
        self.health = ConnectionHealth()
        self.deliveries = DeliveryTracker()
        self.queue: Queue = Queue()
        self.busy_poll = False
        self.next_poll = time.monotonic() + 2
        self.last_error = ''
        self.variables = {}
        self.entity_names = {}
        try:
            self.route_records = read_routes(self.settings.emergency_routes)
        except (ValueError, TypeError):
            self.route_records = []
            self.settings.enable_emergency_contacts = False
            self.settings.emergency_routes = []
        self.notification_targets = []
        self.accessible_size = 15 if self.settings.large_text else 11
        self.build()
        root.after(250, self.process_queue)
        root.after(1000, self.periodic)

    def var(self, name: str, kind='str'):
        value = getattr(self.settings, name)
        obj = tk.BooleanVar(value=value) if kind == 'bool' else tk.StringVar(value=str(value))
        self.variables[name] = obj
        return obj

    def build(self):
        font = ('Segoe UI', self.accessible_size)
        style = ttk.Style()
        style.configure('TButton', padding=7, font=font)
        style.configure('TLabel', font=font)
        style.configure('TCheckbutton', font=font)
        style.configure('TEntry', font=font)
        style.configure('TCombobox', font=font)
        style.configure('TLabelframe.Label', font=('Segoe UI', self.accessible_size, 'bold'))
        self.status = tk.StringVar(value='Not connected — setup required')
        ttk.Label(self.root, text=f'LibreBeacon {__version__}  |  WIP · NOT A MEDICAL ALARM',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=15, pady=(8, 2))
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill='both', expand=True, padx=13, pady=7)
        self.dashboard = ttk.Frame(self.tabs, padding=15)
        self.setup = ttk.Frame(self.tabs, padding=15)
        self.connection = ttk.Frame(self.tabs, padding=15)
        self.sensors = ttk.Frame(self.tabs, padding=15)
        self.access = ttk.Frame(self.tabs, padding=15)
        self.contacts = ttk.Frame(self.tabs, padding=15)
        self.emergency = ttk.Frame(self.tabs, padding=15)
        self.rules = ttk.Frame(self.tabs, padding=15)
        self.about = ttk.Frame(self.tabs, padding=15)
        for tab, label in ((self.dashboard,'Dashboard'),(self.setup,'Start Here'),(self.connection,'1 · Connection'),
                           (self.sensors,'2 · Sensors'),(self.access,'3 · Accessibility'),
                           (self.contacts,'4 · Alerts'),(self.emergency,'5 · Emergency contacts'),(self.rules,'6 · Alert rules'),
                           (self.about,'About')):
            self.tabs.add(tab, text=label)
        self.build_dashboard()
        self.build_setup()
        self.build_connection()
        self.build_sensors()
        self.build_access()
        self.build_contacts()
        self.build_emergency()
        self.build_rules()
        self.build_about()
        ttk.Separator(self.root).pack(fill='x')
        ttk.Label(self.root, textvariable=self.status, wraplength=770).pack(fill='x', padx=14, pady=10)

    @staticmethod
    def line(parent, title, var, row, width=53, password=False, choices=None):
        ttk.Label(parent, text=title).grid(row=row,column=0,sticky='w',padx=(2,14),pady=7)
        if choices is None:
            widget = ttk.Entry(parent, textvariable=var, width=width, show='*' if password else '')
        else:
            widget = ttk.Combobox(parent,textvariable=var,values=choices,width=width)
        widget.grid(row=row,column=1,sticky='ew',pady=7)
        parent.columnconfigure(1,weight=1)
        return widget

    def build_dashboard(self):
        p = self.dashboard
        ttk.Label(p, text='Glucose', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        self.number = tk.StringVar(value='— mmol/L')
        ttk.Label(p, textvariable=self.number, font=('Segoe UI', 42, 'bold')).pack(anchor='w',pady=7)
        self.details = tk.StringVar(value='Connect Home Assistant and choose both sensors.')
        ttk.Label(p, textvariable=self.details,wraplength=740).pack(anchor='w',pady=(0,16))
        bar = ttk.Frame(p)
        bar.pack(fill='x',pady=5)
        ttk.Button(bar,text='Refresh Reading',command=self.manual_refresh).pack(side='left',padx=5)
        ttk.Button(bar,text='Open Setup Guide',command=lambda:self.tabs.select(self.setup)).pack(side='left',padx=5)
        self.enable = self.var('enabled','bool')
        ttk.Checkbutton(p,text='Enable supplementary alerts (OFF by default)',variable=self.enable,
                        command=self.toggle_enabled).pack(anchor='w',pady=12)
        self.connection_health = tk.StringVar(value='Reading health: not checked')
        ttk.Label(p,textvariable=self.connection_health,wraplength=740,
                  font=('Segoe UI',self.accessible_size,'bold')).pack(anchor='w',pady=7)
        ttk.Label(p,text='LibreBeacon only works whilst this Windows app is open and connected. '
                  'Keep your official Libre app and alarms enabled.',wraplength=730).pack(anchor='w')
        self.event_label = tk.StringVar(value='No alerts triggered in this session.')
        ttk.Label(p,textvariable=self.event_label,wraplength=720).pack(anchor='w',pady=18)

    def build_setup(self):
        p = self.setup
        ttk.Label(p, text='Start here — set up without editing files',
                  font=('Segoe UI', 17, 'bold')).pack(anchor='w', pady=8)
        ttk.Label(p, text='Complete the numbered steps below, use each Test button, '
                  'and return here to check the saved settings. The app will not turn on '
                  'automatic warnings or messages for you.', wraplength=750).pack(anchor='w', pady=7)
        for label, tab in (("1. Connect Home Assistant", self.connection),
                           ("2. Find and test both sensors", self.sensors),
                           ("3. Test sound, speech and visual notices", self.access),
                           ("4. Configure optional smart-home alerts", self.contacts),
                           ("5. Add and test trusted contacts", self.emergency),
                           ("6. Set agreed glucose thresholds", self.rules)):
            ttk.Button(p, text=label, command=lambda target=tab: self.tabs.select(target)).pack(
                fill='x', anchor='w', pady=2)
        ttk.Button(p, text='Check Saved Setup', command=self.refresh_setup).pack(anchor='w', pady=10)
        self.setup_report = tk.StringVar()
        ttk.Label(p, textvariable=self.setup_report, wraplength=750,
                  justify='left').pack(anchor='w', pady=5)
        self.refresh_setup()

    def refresh_setup(self):
        checks = setup_checks(self.settings, bool(self.session_token or load_token()))
        lines = [f'{"CONFIGURED" if item.ready else "TO DO"}: {item.title} — {item.explanation}'
                 for item in checks]
        lines.append('These checks inspect saved settings, not live medical reliability. '
                     'Use Test Connection and Test Reading separately.')
        if hasattr(self, 'setup_report'):
            self.setup_report.set('\n\n'.join(lines))

    def update_health_display(self):
        report = self.health.report(datetime.now(timezone.utc), self.settings.freshness_minutes)
        self.connection_health.set(f'Reading health: {report.state} — {report.detail}')
        if report.state in ('STALE', 'CLOCK ERROR', 'UNAVAILABLE'):
            self.number.set('— mmol/L')
            self.details.set('Live measurement unavailable; check the official Libre app.')

    def build_connection(self):
        p = self.connection
        box=ttk.LabelFrame(p,text='Step 1 — Home Assistant connection',padding=14)
        box.pack(fill='x')
        self.line(box,'Server URL',self.var('ha_url'),0)
        self.token_var=tk.StringVar(value='')
        self.line(box,'Long-lived access token',self.token_var,1,password=True)
        ttk.Label(box,text='Stored in Windows Credential Manager via Python keyring; not in the settings file.',
                  wraplength=720).grid(row=2,column=0,columnspan=2,sticky='w',pady=5)
        bar=ttk.Frame(box)
        bar.grid(row=3,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Button(bar,text='Save Connection',command=self.save_connection).pack(side='left',padx=4)
        ttk.Button(bar,text='Test Connection',command=self.test_connection).pack(side='left',padx=4)
        ttk.Button(bar,text='Open Home Assistant',command=self.open_ha).pack(side='left',padx=4)
        box2=ttk.LabelFrame(p,text='Optional Windows Phone Link',padding=14)
        box2.pack(fill='x',pady=18)
        ttk.Label(box2,text='Phone Link can mirror notifications, but does not provide a supported API '
                  'for LibreBeacon to read their contents.',wraplength=720).pack(anchor='w')
        ttk.Button(box2,text='Open Microsoft Phone Link Setup Guide',
                   command=lambda:webbrowser.open(HELP_URL)).pack(anchor='w',pady=9)

    def build_sensors(self):
        p=self.sensors
        box=ttk.LabelFrame(p,text='Step 2 — Select both Home Assistant sensors',padding=14)
        box.pack(fill='x')
        ttk.Label(box,text='Use an existing LibreLinkUp integration. The second sensor MUST be the actual '
                  'measurement timestamp, not Home Assistant last_updated.',wraplength=730).grid(
                      row=0,column=0,columnspan=2,sticky='w',pady=10)
        self.glucose=self.var('glucose_entity')
        self.timestamp=self.var('timestamp_entity')
        self.glucose_combo=self.line(box,'Glucose entity',self.glucose,1,choices=[])
        self.timestamp_combo=self.line(box,'Last Reading timestamp',self.timestamp,2,choices=[])
        bar=ttk.Frame(box)
        bar.grid(row=3,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Button(bar,text='Find Sensors',command=self.find_sensors).pack(side='left',padx=4)
        ttk.Button(bar,text='Save Sensor Selection',command=self.save_sensors).pack(side='left',padx=4)
        ttk.Button(bar,text='Test Reading',command=self.manual_refresh).pack(side='left',padx=4)

    def build_access(self):
        p=self.access
        box=ttk.LabelFrame(p,text='Step 3 — Local accessibility',padding=14)
        box.pack(fill='x')
        for name,label in [('enable_sound','Audible warning tone'),('enable_speech','Spoken warning (Windows offline speech)'),
                           ('enable_visual','Large visual warning with slow colour pulses'),('large_text','Large text')]:
            ttk.Checkbutton(box,text=label,variable=self.var(name,'bool')).pack(anchor='w',pady=5)
        bar=ttk.Frame(box)
        bar.pack(fill='x',pady=10)
        ttk.Button(bar,text='Test Audible Alarm',command=self.test_sound).pack(side='left',padx=4)
        ttk.Button(bar,text='Test Spoken Message',command=self.test_speech).pack(side='left',padx=4)
        ttk.Button(bar,text='Test Visual Alert',command=self.test_visual).pack(side='left',padx=4)
        ttk.Button(box,text='Save Accessibility Settings',command=self.save_general).pack(anchor='w',pady=5)
        ttk.Label(box,text='Large-text changes take effect after restarting the application. '
                  'Flashing uses slow pulses; use steady-only visual alerts if flashing is unsuitable.',
                  wraplength=720).pack(anchor='w',pady=8)

    def build_contacts(self):
        p=self.contacts
        visual=ttk.LabelFrame(p,text='Step 4A — Home Assistant visual alert',padding=12)
        visual.pack(fill='x',pady=7)
        ttk.Label(visual,text='Choose a Home Assistant script to run smart lights, speakers or other effects. '
                  'Create and test that script inside Home Assistant first.',wraplength=735).pack(anchor='w')
        self.visual_script=self.var('visual_script')
        self.visual_combo=ttk.Combobox(visual,textvariable=self.visual_script,width=65)
        self.visual_combo.pack(fill='x',pady=5)
        ttk.Checkbutton(visual,text='Enable this visual script',variable=self.var('enable_ha_visual','bool')).pack(anchor='w')
        btn=ttk.Frame(visual);btn.pack(anchor='w',pady=8)
        ttk.Button(btn,text='Find Home Assistant Scripts',command=self.find_sensors).pack(side='left',padx=3)
        ttk.Button(btn,text='Test Visual Script',command=lambda:self.test_script('visual')).pack(side='left',padx=3)
        ttk.Button(btn,text='Open Home Assistant',command=self.open_ha).pack(side='left',padx=3)
        contact=ttk.LabelFrame(p,text='Step 4B — Contact messaging',padding=12)
        contact.pack(fill='x',pady=7)
        ttk.Label(contact,text='Select an existing Home Assistant script which sends an email or message. '
                  'Contact addresses are configured in Home Assistant, never stored here.',wraplength=730).grid(row=0,column=0,columnspan=2,sticky='w',pady=5)
        self.line(contact,'Contact label',self.var('contact_label'),1)
        self.contact_script=self.var('contact_script')
        self.contact_combo=self.line(contact,'Message script',self.contact_script,2,choices=[])
        ttk.Checkbutton(contact,text='Enable supplementary contact messages',
                        variable=self.var('enable_contacts','bool')).grid(row=3,column=0,columnspan=2,sticky='w')
        ttk.Checkbutton(contact,text='I have permission to contact this recipient',
                        variable=self.var('contact_consent','bool')).grid(row=4,column=0,columnspan=2,sticky='w')
        bar=ttk.Frame(contact);bar.grid(row=5,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Button(bar,text='Save Notification Settings',command=self.save_general).pack(side='left',padx=4)
        ttk.Button(bar,text='Test Contact Message',command=lambda:self.test_script('contact')).pack(side='left',padx=4)
        ttk.Label(contact,text='Sending a message does NOT prove it arrived or was read. '
                  'Only test with the contact’s consent.',wraplength=720).grid(row=6,column=0,columnspan=2,sticky='w')

    def build_emergency(self):
        p = self.emergency
        box = ttk.LabelFrame(p, text='Step 5 — Additional critical-low contact routes', padding=12)
        box.pack(fill='both', expand=True)
        ttk.Label(box, text='Choose the destination in Home Assistant, then add it here. '
                  'It can be a mobile notification, a message script or a Meshtastic node. '
                  'Nothing sends automatically until you explicitly enable it.',
                  wraplength=780).pack(anchor='w', pady=5)
        self.route_list = tk.Listbox(box, height=6, font=('Segoe UI', max(10, self.accessible_size - 1)))
        self.route_list.pack(fill='x', pady=5)
        self.refresh_routes()
        self.route_label = tk.StringVar()
        self.route_target = tk.StringVar()
        self.route_consent = tk.BooleanVar(value=False)
        entry_box = ttk.Frame(box); entry_box.pack(fill='x')
        self.line(entry_box, 'Contact nickname', self.route_label, 0, width=47)
        self.route_combo = self.line(entry_box, 'Home Assistant destination', self.route_target, 1,
                                     width=47, choices=[])
        ttk.Checkbutton(box, text='This contact has agreed to receive tests and critical-low messages',
                        variable=self.route_consent).pack(anchor='w', pady=4)
        bar = ttk.Frame(box); bar.pack(anchor='w', pady=5)
        ttk.Button(bar, text='Find Destinations', command=self.find_sensors).pack(side='left', padx=3)
        ttk.Button(bar, text='Show Mesh Nodes', command=self.show_mesh_destinations).pack(side='left', padx=3)
        ttk.Button(bar, text='Add Contact', command=self.add_emergency_route).pack(side='left', padx=3)
        ttk.Button(bar, text='Remove Selected', command=self.remove_emergency_route).pack(side='left', padx=3)
        ttk.Button(bar, text='Test Selected', command=self.test_emergency_route).pack(side='left', padx=3)
        ttk.Button(bar, text='Record Recipient Reply', command=self.confirm_emergency_route).pack(side='left', padx=3)
        self.emergency_enabled = self.var('enable_emergency_contacts', 'bool')
        self.emergency_consent = self.var('emergency_contact_consent', 'bool')
        self.include_value = self.var('include_glucose_in_messages', 'bool')
        ttk.Checkbutton(box, text='Enable automatic critical-low contact messages',
                        variable=self.emergency_enabled).pack(anchor='w', pady=5)
        ttk.Checkbutton(box, text='I understand delivery is not guaranteed, and recipients agreed',
                        variable=self.emergency_consent).pack(anchor='w', pady=3)
        ttk.Checkbutton(box, text='Include the glucose value in contact messages (optional; privacy)',
                        variable=self.include_value).pack(anchor='w', pady=3)
        helpbar = ttk.Frame(box); helpbar.pack(anchor='w', pady=6)
        ttk.Button(helpbar, text='Save Emergency Contact Settings', command=self.save_general).pack(side='left', padx=3)
        ttk.Button(helpbar, text='Help Choosing a Destination', command=self.contact_help).pack(side='left', padx=3)
        ttk.Label(box, text='Meshtastic: install the Meshtastic integration in Home Assistant, '
                  'select an individual notify.mesh_* destination rather than a broadcast channel, '
                  'then test it with the recipient. No message guarantees someone has received it.',
                  wraplength=790).pack(anchor='w', pady=4)

    def refresh_routes(self):
        self.route_list.delete(0, tk.END)
        for route in self.route_records:
            note = self.deliveries.description(route.target)
            self.route_list.insert(tk.END, f'{route.label}  •  {route.target}  [{note}]')

    def show_mesh_destinations(self):
        matches = [e for e in self.notification_targets if e.startswith('notify.mesh_')]
        self.route_combo.configure(values=matches)
        self.status.set(f'Found {len(matches)} possible Meshtastic destinations. '
                        'Choose a private node, not a channel or broadcast.')

    def contact_help(self):
        messagebox.showinfo('Emergency contact setup',
            '1. Open Home Assistant and set up a phone, email or Meshtastic notification destination.\n'
            '2. Return here and press Find Destinations.\n'
            '3. Enter a contact nickname and choose one notify.* entity or script.* entity.\n'
            '4. Tick consent, press Add Contact, then Save.\n'
            '5. Select the contact and press Test Selected. Ask them to confirm it arrived.\n'
            '6. Set a critical-low threshold in Alert rules and explicitly enable contact messages.\n\n'
            'Sending does not prove delivery. Always keep the official Libre alarms on.')

    def add_emergency_route(self):
        try:
            route = ContactRoute(self.route_label.get().strip(), self.route_target.get().strip(),
                                 bool(self.route_consent.get()), True).validate()
            read_routes([r.as_dict() for r in self.route_records] + [route.as_dict()])
        except ValueError as exc:
            messagebox.showerror('Contact', str(exc)); return
        self.route_records.append(route)
        self.refresh_routes()
        self.route_label.set(''); self.route_target.set(''); self.route_consent.set(False)
        self.status.set('Contact added locally. Save Emergency Contact Settings to keep this change.')

    def remove_emergency_route(self):
        picked = self.route_list.curselection()
        if not picked: return
        if not messagebox.askyesno('Remove contact', 'Remove this notification destination?'): return
        self.route_records.pop(picked[0])
        self.refresh_routes()
        self.status.set('Contact removed locally. Save settings to keep this change.')

    def test_emergency_route(self):
        picked = self.route_list.curselection()
        if not picked:
            messagebox.showinfo('Test contact', 'Select a contact first.'); return
        route = self.route_records[picked[0]]
        if not messagebox.askyesno('Send real test',
            f'This will send a test to {route.label}. Have they agreed, and can they confirm receipt?'):
            return
        try: client = self.client()
        except HomeAssistantError as exc:
            messagebox.showerror('Connection', str(exc)); return
        from .contacts import dispatch_route
        def attempt():
            try:
                dispatch_route(client, route, 'LibreBeacon TEST ONLY. No glucose emergency has occurred.')
                return route.target, True
            except Exception:
                return route.target, False
        self.start('emergency_test', attempt)

    def confirm_emergency_route(self):
        picked = self.route_list.curselection()
        if not picked:
            messagebox.showinfo('Contact confirmation', 'Select a contact first.'); return
        route = self.route_records[picked[0]]
        if not messagebox.askyesno('Record a reply',
            'Have you personally heard back from this recipient by phone or another means? '
            'This only records what you report; LibreBeacon cannot verify a person saw a message.'):
            return
        try:
            self.deliveries.confirm(route.target)
        except ValueError as exc:
            messagebox.showinfo('No successful request yet', str(exc)); return
        self.refresh_routes()
        self.status.set('Recipient reply marked manually for this session. '
                        'This is not an automatic delivery receipt.')

    def build_rules(self):
        p=self.rules
        box=ttk.LabelFrame(p,text='Step 6 — Supplementary alert conditions',padding=15)
        box.pack(fill='x')
        self.line(box,'Low threshold (mmol/L)',self.var('low_mmol'),0,width=20)
        self.line(box,'High threshold (mmol/L)',self.var('high_mmol'),1,width=20)
        self.line(box,'Critical-low contact threshold (mmol/L; optional)',
                  self.var('critical_low_mmol'),2,width=20)
        self.line(box,'Maximum reading age (minutes)',self.var('freshness_minutes'),3,width=20)
        self.line(box,'Minimum pause between events (minutes)',self.var('cooldown_minutes'),4,width=20)
        self.line(box,'Check interval (seconds)',self.var('poll_seconds'),5,width=20)
        ttk.Label(box,text='Thresholds are deliberately blank. Choose them with the person and their '
                  'healthcare team; this app must not be the source of clinical thresholds.',wraplength=740).grid(
                      row=6,column=0,columnspan=2,sticky='w',pady=8)
        ttk.Button(box,text='Save and Validate Alert Rules',command=self.save_rules).grid(
            row=7,column=0,columnspan=2,sticky='w',pady=10)

    def build_about(self):
        ttk.Label(self.about,text=f'LibreBeacon {__version__} — experimental accessibility companion',
                  font=('Segoe UI',17,'bold')).pack(anchor='w',pady=10)
        ttk.Label(self.about,text='Not a medical device. Not approved to detect or treat hypoglycaemia or '
                  'hyperglycaemia. Do not use as your sole warning system or for treatment decisions. '
                  'Do not disable LibreLink / LibreLinkUp alerts. It can miss data, fail to speak, '
                  'lose Internet access or fail to deliver messages. It only monitors whilst running.',
                  wraplength=730).pack(anchor='w',pady=10)
        ttk.Label(self.about,text='LibreBeacon is independently developed and is not affiliated with '
                  'Abbott, Microsoft or Home Assistant. It reads Home Assistant’s published API.').pack(
                      anchor='w',pady=12)

    def collect(self):
        from dataclasses import fields
        bool_names={'enabled','enable_sound','enable_visual','enable_speech','enable_ha_visual',
                    'enable_contacts','contact_consent','large_text',
                    'enable_emergency_contacts','emergency_contact_consent','include_glucose_in_messages'}
        int_names={'freshness_minutes','poll_seconds','cooldown_minutes'}
        values={}
        for f in fields(Settings):
            raw=self.variables[f.name].get() if f.name in self.variables else getattr(self.settings,f.name)
            if f.name in bool_names: raw=bool(raw)
            elif f.name in int_names: raw=int(raw)
            values[f.name]=raw
        values['emergency_routes'] = [r.as_dict() for r in self.route_records]
        return Settings(**values)

    @staticmethod
    def validate(s: Settings, require_enabled: bool = False):
        if not 3 <= s.freshness_minutes <= 60:
            raise ValueError('Reading age must be 3–60 minutes')
        if not 30 <= s.poll_seconds <= 900:
            raise ValueError('Check interval must be 30–900 seconds')
        if not 1 <= s.cooldown_minutes <= 1440:
            raise ValueError('Pause must be 1–1440 minutes')
        from .contacts import read_routes
        routes = read_routes(s.emergency_routes)
        if s.enable_emergency_contacts:
            if not s.emergency_contact_consent or not routes:
                raise ValueError('Add consented emergency contacts and accept the contact delivery warning')
            if not s.critical_low_mmol:
                raise ValueError('Set a critical-low threshold before enabling emergency messages')
        if s.critical_low_mmol:
            if not s.low_mmol:
                raise ValueError('Set a standard low threshold before the critical-low threshold')
            critical, normal_low = float(s.critical_low_mmol), float(s.low_mmol)
            if not (0 < critical < normal_low):
                raise ValueError('Critical-low threshold must be below the low threshold')
        if s.enable_contacts and not s.contact_consent:
            raise ValueError('Confirm the contact has agreed to receive messages')
        if s.enabled or require_enabled:
            if not s.ha_url or not s.glucose_entity or not s.timestamp_entity:
                raise ValueError('First connect Home Assistant and choose both sensors')
            if not s.low_mmol or not s.high_mmol:
                raise ValueError('Set both threshold values before enabling alerts')
            lo,hi=float(s.low_mmol),float(s.high_mmol)
            if not 0 < lo < hi <= 60:
                raise ValueError('Thresholds must be ordered and valid')
            if s.enable_ha_visual and not s.visual_script.startswith('script.'):
                raise ValueError('Choose a visual alert script')
            if s.enable_contacts and not s.contact_script.startswith('script.'):
                raise ValueError('Choose a contact notification script')
            if s.enable_contacts and not s.contact_consent:
                raise ValueError('Confirm the contact has agreed to receive messages')

    def save_general(self):
        try:
            s=self.collect();self.validate(s)
            s.save();self.settings=s
            self.status.set('Settings saved. Live changes apply on the next reading.')
            self.refresh_setup()
        except (ValueError, OSError) as exc:
            messagebox.showerror('Check Settings',str(exc))

    def save_rules(self):
        self.save_general()

    def save_sensors(self):
        self.save_general()

    def save_connection(self):
        self.settings.ha_url=self.variables['ha_url'].get().strip()
        if not self.settings.ha_url:
            messagebox.showerror('Connection','Enter the Home Assistant URL first.');return
        entered=self.token_var.get().strip()
        if entered:
            self.session_token=entered
            try:
                save_token(entered)
                self.token_var.set('')
                self.status.set('Connection saved; token stored securely in the OS credential vault.')
            except Exception:
                messagebox.showwarning('Token not stored','Token will work for this session only. '
                    'Install keyring and verify that a secure credential backend is available.')
        self.settings.save()
        self.refresh_setup()

    def toggle_enabled(self):
        try:
            s=self.collect();self.validate(s)
            if s.enabled and not (self.session_token or load_token()):
                raise ValueError('Save an access token in Connection first')
            self.settings=s;self.settings.save();self.engine=AlertEngine()
            self.status.set('Supplementary alerts ENABLED' if s.enabled else 'Supplementary alerts paused')
        except (ValueError,OSError) as exc:
            self.enable.set(False)
            messagebox.showerror('Cannot enable alerts',str(exc))

    def client(self):
        return HomeAssistant(self.variables['ha_url'].get().strip(),
                             self.token_var.get().strip() or self.session_token or load_token())

    def start(self, key, fn):
        def job():
            try: self.queue.put((key,True,fn()))
            except Exception as exc: self.queue.put((key,False,str(exc)))
        Thread(target=job, daemon=True).start()

    def test_connection(self):
        try: c=self.client()
        except HomeAssistantError as exc:messagebox.showerror('Connection',str(exc));return
        self.status.set('Checking connection…')
        self.start('connection', lambda:c.request('GET','config'))

    def find_sensors(self):
        try: c=self.client()
        except HomeAssistantError as exc:messagebox.showerror('Connection',str(exc));return
        self.status.set('Finding Home Assistant entities…')
        self.start('entities', c.states)

    def manual_refresh(self):
        try:
            c=self.client()
            glucose=self.glucose.get().strip()
            timestamp=self.timestamp.get().strip()
            if not glucose or not timestamp:
                raise ValueError('Select both the glucose and the last-reading timestamp entity')
        except (HomeAssistantError,ValueError) as exc:messagebox.showerror('Reading',str(exc));return
        self.status.set('Checking current glucose reading…')
        self.start('reading', lambda:(c.state(glucose),c.state(timestamp)))

    def periodic(self):
        if self.settings.ha_url and self.settings.glucose_entity and self.settings.timestamp_entity \
            and not self.busy_poll and time.monotonic() >= self.next_poll:
            self.busy_poll=True
            self.next_poll=time.monotonic()+self.settings.poll_seconds
            try:
                c=HomeAssistant(self.settings.ha_url, self.session_token or load_token())
                a,b=self.settings.glucose_entity,self.settings.timestamp_entity
                self.start('poll',lambda:(c.state(a),c.state(b)))
            except HomeAssistantError as exc:
                self.busy_poll=False
                self.status.set(str(exc))
        self.update_health_display()
        self.root.after(1000,self.periodic)

    def process_queue(self):
        try:
            while True:
                key,ok,result=self.queue.get_nowait()
                if key=='poll':self.busy_poll=False
                if not ok:
                    self.status.set(f'{key}: {result}')
                    if key in ('reading','poll'):
                        self.health.failure(datetime.now(timezone.utc))
                        self.update_health_display()
                        self.number.set('— mmol/L')
                        self.details.set('READING UNAVAILABLE — do not rely on this display.')
                    continue
                if key=='connection':
                    self.status.set('Connected to Home Assistant successfully.')
                elif key=='entities':
                    entities=result
                    glucose=[e['entity_id'] for e in entities if e.get('entity_id','').startswith('sensor.')
                             and ('glucose' in e['entity_id'] or 'blood_glucose_concentration' == e.get('attributes',{}).get('device_class'))]
                    stamps=[e['entity_id'] for e in entities if e.get('entity_id','').startswith('sensor.')
                            and (e.get('attributes',{}).get('device_class')=='timestamp' or
                                 'last_reading' in e['entity_id'])]
                    scripts=[e['entity_id'] for e in entities if e.get('entity_id','').startswith('script.')]
                    notifications=[e['entity_id'] for e in entities if e.get('entity_id','').startswith('notify.')]
                    self.notification_targets=sorted(scripts+notifications)
                    self.glucose_combo.configure(values=glucose)
                    self.timestamp_combo.configure(values=stamps)
                    self.visual_combo.configure(values=scripts)
                    self.contact_combo.configure(values=scripts)
                    self.route_combo.configure(values=self.notification_targets)
                    self.status.set(f'Found {len(glucose)} glucose candidates, {len(stamps)} timestamps and {len(self.notification_targets)} messaging destinations. Choose and save.')
                elif key in ('reading','poll'):
                    self.show_reading(*result, allow_alerts=(key == 'poll'))
                elif key=='emergency_test':
                    destination, accepted = result
                    self.deliveries.record(destination, accepted=accepted, kind='test')
                    self.refresh_routes()
                    self.status.set('Test request accepted; ask the recipient to reply.' if accepted
                                    else 'Contact test request failed; check destination and Home Assistant.')
                elif key=='emergency_delivery':
                    # The service's acknowledgement is not a person's reply.
                    targets = {r.label: r.target for r in self.route_records}
                    for label, accepted, _detail in result:
                        if label in targets:
                            self.deliveries.record(targets[label], accepted=accepted, kind='critical_low')
                    self.refresh_routes()
                    delivered = sum(1 for _, ok, _ in result if ok)
                    failed = sum(1 for _, ok, _ in result if not ok)
                    self.status.set(f'Contact requests accepted: {delivered}; rejected: {failed}. Receipt remains unconfirmed.')
                elif key in ('script','test_script'):
                    self.status.set('Home Assistant accepted the script request. Delivery or activation is not confirmed.')
        except Empty: pass
        self.root.after(250,self.process_queue)

    def show_reading(self,glucose,timestamp, *, allow_alerts=False):
        try:
            reading=decode_reading(glucose,timestamp)
            if hasattr(self, 'health'):
                self.health.success(reading.measured_at, datetime.now(timezone.utc))
            age=reading.age_minutes()
            self.details.set(f'Measured {age:.1f} minutes ago • timestamp from sensor')
            reading.validated(self.settings.freshness_minutes)
            self.number.set(f'{reading.mmol:.1f} mmol/L')
            self.status.set('Reading available and within configured age limit.')
            if hasattr(self, 'health'):
                self.update_health_display()
            if not (allow_alerts and self.settings.enabled):return
            # Do not infer fresh glucose data from last_updated: source timestamp only.
            event=self.engine.observe(reading,float(self.settings.low_mmol),
                     float(self.settings.high_mmol),self.settings.freshness_minutes,
                     cooldown_minutes=self.settings.cooldown_minutes,
                     critical_low=float(self.settings.critical_low_mmol) if self.settings.critical_low_mmol else None)
            if event:
                message=f'Supplementary {event} glucose warning. Reading {reading.mmol:.1f} millimoles per litre. Check the official Libre app.'
                self.event_label.set(f'Latest supplementary event: {event} ({datetime.now().strftime("%H:%M")})')
                # Sending externally is deliberately separate from local alerts.
                self.alert(event,message,reading.mmol)
        except (ReadingError,ValueError) as exc:
            self.number.set('— mmol/L')
            self.details.set(f'DATA NOT VERIFIED: {exc}')
            self.status.set('NO GLUCOSE ALERT ISSUED — missing, malformed or stale reading.')
            if hasattr(self, 'health'):
                self.update_health_display()

    def alert(self,event,message,mmol=None):
        if self.settings.enable_visual:self.popup(f'{event.upper()} READING',message)
        if self.settings.enable_sound:beep()
        if self.settings.enable_speech:start_speech(message)
        if self.settings.enable_ha_visual:self.send_script(self.settings.visual_script,event,message)
        if event == 'critical_low' and self.settings.enable_emergency_contacts:
            routes = read_routes(self.settings.emergency_routes)
            text = emergency_message(self.settings.include_glucose_in_messages, mmol)
            try: client = HomeAssistant(self.settings.ha_url, self.session_token or load_token())
            except HomeAssistantError as exc:
                self.status.set(f'Contact sending failed to start: {exc}')
            else:
                def send_all():
                    results = []
                    dispatch_emergency(routes, client, text,
                                       lambda name, ok, detail: results.append((name, ok, detail)))
                    return results
                self.start('emergency_delivery', send_all)
        elif self.settings.enable_contacts:
            # Older contact scripts stay supported; avoid exposing the actual
            # glucose number unless the person deliberately opted into it.
            contact_text = f'LibreBeacon supplementary {event} glucose warning. Check the person and their approved monitoring app.'
            if self.settings.include_glucose_in_messages and mmol is not None:
                contact_text += f' Reading: {mmol:.1f} mmol/L.'
            self.send_script(self.settings.contact_script,event,contact_text)

    def popup(self,title,message):
        pop=tk.Toplevel(self.root)
        pop.title('LibreBeacon visual notice — supplementary only')
        pop.geometry('620x300')
        pop.transient(self.root)
        pop.configure(bg='#7c1820')
        lab=tk.Label(pop,text=title+'\n\n'+message,fg='white',bg='#7c1820',
                     font=('Segoe UI',23,'bold'),wraplength=570,justify='center')
        lab.pack(fill='both',expand=True,padx=18,pady=14)
        tk.Button(pop,text='CLOSE VISUAL NOTICE',font=('Segoe UI',18,'bold'),
                  command=pop.destroy).pack(pady=12)
        def pulse(step=0):
            if not pop.winfo_exists() or step>=6:return
            colour='#351016' if step%2 else '#7c1820'
            pop.configure(bg=colour);lab.configure(bg=colour)
            pop.after(1100, lambda:pulse(step+1))
        pulse()

    def test_sound(self):
        beep()
        if not (self.settings.enable_sound):
            self.status.set('Test tone requested, even though sound is currently disabled for automatic alerts.')

    def test_speech(self):
        start_speech('This is a test of the LibreBeacon spoken notification.')
        self.status.set('Speech test requested. Requires Windows speech components and unmuted audio.')

    def test_visual(self):
        self.popup('TEST ONLY','This is an accessibility display test. No glucose event has occurred.')

    def send_script(self,script,event,message,test=False):
        try:
            client = self.client() if test else HomeAssistant(
                self.settings.ha_url, self.session_token or load_token())
        except HomeAssistantError as exc:
            self.status.set(f'Cannot send Home Assistant action: {exc}');return
        self.start('test_script' if test else 'script',
                   lambda:client.run_script(script,event=event,message=message))

    def test_script(self,kind):
        script=(self.visual_script if kind=='visual' else self.contact_script).get().strip()
        if not script.startswith('script.'):
            messagebox.showerror('Script','Choose a Home Assistant script first.');return
        if kind=='contact':
            if not messagebox.askyesno('Confirm external test','This may send an external message to a real person. '
                   'Confirm that you have their permission. Send a clearly labelled TEST message?'):return
        else:
            if not messagebox.askyesno('Test visual script','This may switch on smart lights or other devices. Run the test?'):return
        self.send_script(script,'test','LibreBeacon TEST ONLY. No glucose emergency has occurred.',test=True)

    def open_ha(self):
        url=self.variables['ha_url'].get().strip()
        if url.startswith(('http://','https://')):webbrowser.open(url)
        else:messagebox.showinfo('Home Assistant','Enter the Home Assistant base URL first.')


def main():
    root=tk.Tk()
    LibreBeaconApp(root)
    root.mainloop()

if __name__=='__main__':
    main()
