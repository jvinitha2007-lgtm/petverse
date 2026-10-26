import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowRight, BadgeCheck, Bell, CalendarDays, Check, ChevronDown, CircleHelp,
  Clock3, FileHeart, Heart, LayoutDashboard, LogOut, Menu, PawPrint, Plus,
  MessageCircle, Search, Send, ShieldAlert, ShieldCheck, Sparkles, Stethoscope, UserRoundCheck, X, Home,
} from "lucide-react";
import AuthScreen from "./components/AuthScreen";
import { useAuth } from "./contexts/AuthContext";
import { api } from "./services/api";
import type {
  AdoptionListing, AdminUser, AppNotification, Appointment, CareTask, ChatMessage, Conversation, DashboardData,
  EmergencyCategory, EmergencyRequest, MedicalRecord, Pet, ProfessionalApplication, ProfessionalRole,
  MissingPetReport, PetSighting, ProviderAvailability, ProviderProfile, VolunteerProfile,
} from "./types";

type Page = "overview" | "pets" | "care" | "records" | "assistant" | "verification" | "administration" | "discover" | "provider" | "emergency" | "messages" | "notifications" | "community";

const navItems: { id: Page; label: string; icon: typeof LayoutDashboard; adminOnly?: boolean }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "pets", label: "My pets", icon: PawPrint },
  { id: "care", label: "Care calendar", icon: CalendarDays },
  { id: "records", label: "Health records", icon: FileHeart },
  { id: "assistant", label: "Care assistant", icon: Sparkles },
  { id: "messages", label: "Messages", icon: MessageCircle },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "emergency", label: "Emergency help", icon: ShieldAlert },
  { id: "community", label: "Adoption & lost pets", icon: Home },
  { id: "verification", label: "Professional access", icon: UserRoundCheck },
  { id: "discover", label: "Find a provider", icon: Stethoscope },
  { id: "provider", label: "Provider workspace", icon: CalendarDays },
  { id: "administration", label: "Admin review", icon: BadgeCheck, adminOnly: true },
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value));
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
}

export default function App() {
  const { user, loading, signOut } = useAuth();
  const [page, setPage] = useState<Page>("overview");
  const [pets, setPets] = useState<Pet[]>([]);
  const [tasks, setTasks] = useState<CareTask[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [selectedPet, setSelectedPet] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [petFormOpen, setPetFormOpen] = useState(false);
  const [petToEdit, setPetToEdit] = useState<Pet | null>(null);
  const [taskFormOpen, setTaskFormOpen] = useState(false);
  const [recordFormOpen, setRecordFormOpen] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const visibleNav = navItems.filter((item) => {
    if (item.id === "overview" || item.id === "messages" || item.id === "notifications") return true;
    if (user?.role === "owner") {
      return ["pets", "care", "records", "assistant", "discover", "emergency", "community", "verification"].includes(item.id);
    }
    if (user?.role === "veterinarian" || user?.role === "groomer") {
      return item.id === "provider" || item.id === "verification";
    }
    if (user?.role === "volunteer") return item.id === "emergency" || item.id === "community" || item.id === "verification";
    if (user?.role === "shelter") return item.id === "community" || item.id === "verification";
    if (user?.role === "admin") return item.id === "administration" || item.id === "emergency" || item.id === "community";
    return item.id === "verification";
  });
  const notifyError = useCallback((message: string) => setError(message), []);
  const notifySuccess = useCallback((message: string) => setSuccess(message), []);

  const refreshData = useCallback(async () => {
    try {
      const [petData, taskData, dashboardData] = await Promise.all([api.pets(), api.tasks(), api.dashboard()]);
      setPets(petData);
      setTasks(taskData);
      setDashboard(dashboardData);
      setSelectedPet((current) => current && petData.some((pet) => pet.id === current) ? current : petData[0]?.id ?? null);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load your care information.");
    }
  }, []);

  useEffect(() => {
    if (user) void refreshData();
  }, [user, refreshData]);

  useEffect(() => {
    if (!user) {
      setUnreadNotifications(0);
      return;
    }
    api.notifications().then((items) => setUnreadNotifications(items.filter((item) => !item.is_read).length))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to load notifications."));
  }, [user, page]);

  useEffect(() => {
    if (!user || !selectedPet) {
      setRecords([]);
      return;
    }
    api.records(selectedPet).then(setRecords).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Unable to load health records.");
    });
  }, [user, selectedPet]);

  const petById = useMemo(() => new Map(pets.map((pet) => [pet.id, pet])), [pets]);

  async function submitPet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const payload = {
      name: String(data.get("name")),
      species: String(data.get("species")),
      breed: String(data.get("breed")) || null,
      birth_date: String(data.get("birth_date")) || null,
      sex: String(data.get("sex")) || null,
      weight_kg: data.get("weight") ? Number(data.get("weight")) : null,
      allergies: String(data.get("allergies")) || null,
      notes: String(data.get("notes")) || null,
    };
    try {
      const pet = petToEdit
        ? await api.updatePet(petToEdit.id, payload)
        : await api.createPet(payload);
      await refreshData();
      setSelectedPet(pet.id);
      setPetFormOpen(false);
      setPetToEdit(null);
      setSuccess(petToEdit ? `${pet.name}'s profile was updated.` : `${pet.name} is part of your care circle.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't add this pet.");
    }
  }

  async function submitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const petId = Number(data.get("pet_id"));
    try {
      await api.createTask({
        pet_id: petId,
        title: String(data.get("title")),
        category: String(data.get("category")),
        instructions: String(data.get("instructions")) || null,
        due_at: new Date(String(data.get("due_at"))).toISOString(),
        repeat_interval_minutes: data.get("repeat_interval_minutes")
          ? Number(data.get("repeat_interval_minutes")) : null,
        reminder_days_before: Number(data.get("reminder_days_before")),
      });
      await refreshData();
      setTaskFormOpen(false);
      setSuccess("Care reminder added.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't add this reminder.");
    }
  }

  async function submitRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPet) return;
    const data = new FormData(event.currentTarget);
    try {
      await api.createRecord(selectedPet, {
        record_type: String(data.get("record_type")),
        title: String(data.get("title")),
        details: String(data.get("details")),
      });
      setRecords(await api.records(selectedPet));
      setRecordFormOpen(false);
      setSuccess("Health note saved as an owner observation.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't save this note.");
    }
  }

  async function completeTask(task: CareTask) {
    try {
      await api.completeTask(task.id);
      await refreshData();
      setSuccess("Care task marked complete.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't update this task.");
    }
  }

  async function archivePet(pet: Pet) {
    if (!window.confirm(`Archive ${pet.name}'s profile? Their records will be retained but hidden.`)) return;
    try {
      await api.archivePet(pet.id);
      await refreshData();
      setSuccess(`${pet.name}'s profile was archived.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Couldn't archive this pet.");
    }
  }

  if (loading) return <div className="loading-screen"><div className="loading-mark"><Heart fill="currentColor" /></div><span>Opening your care corner…</span></div>;
  if (!user) return <AuthScreen />;

  const displayName = user.full_name.split(" ")[0];
  const activePet = petById.get(selectedPet ?? -1);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="sidebar-brand">
          <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setPage("overview"); }}>
            <span className="brand-mark"><Heart size={18} fill="currentColor" /></span><span>petverse<span className="brand-dot">.</span></span>
          </a>
          <button className="icon-button mobile-close" aria-label="Close menu" onClick={() => setSidebarOpen(false)}><X size={18} /></button>
        </div>
        <div className="workspace-label">YOUR SPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {visibleNav.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-link ${page === id ? "active" : ""}`} onClick={() => { setPage(id); setSidebarOpen(false); }}>
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{id === "care" && tasks.some((task) => !task.completed) && <span className="nav-count">{tasks.filter((task) => !task.completed).length}</span>}
            </button>
          ))}
        </nav>
        {user.role === "owner" && <>
          <div className="sidebar-divider" />
          <div className="side-section-heading"><span>YOUR PETS</span><button aria-label="Add pet" onClick={() => setPetFormOpen(true)}><Plus size={15} /></button></div>
          <div className="sidebar-pets">
            {pets.map((pet, index) => (
              <button key={pet.id} className={`pet-nav-item ${selectedPet === pet.id ? "selected" : ""}`} onClick={() => { setSelectedPet(pet.id); setPage("pets"); setSidebarOpen(false); }}>
                <span className={`tiny-pet pet-color-${index % 4}`}>{pet.species.toLowerCase().includes("cat") ? "🐱" : pet.species.toLowerCase().includes("bird") ? "🐦" : "🐶"}</span>
                <span>{pet.name}</span><span className="pet-nav-dot" />
              </button>
            ))}
            {pets.length === 0 && <p className="sidebar-empty">Your pets will show up here.</p>}
            <button className="add-pet-link" onClick={() => setPetFormOpen(true)}><Plus size={15} /> Add a pet</button>
          </div>
        </>}
        <div className="sidebar-bottom">
          <div className="help-card"><div className="help-icon"><CircleHelp size={17} /></div><div><strong>Here to help</strong><p>Your care corner, all in one place.</p></div></div>
          <button className="profile-menu" onClick={signOut}>
            <span className="profile-avatar">{initials(user.full_name)}</span>
            <span className="profile-details"><strong>{user.full_name}</strong><small>Pet parent</small></span>
            <LogOut size={17} className="logout-icon" />
          </button>
        </div>
      </aside>

      {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open menu" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumb"><span>My space</span><span className="crumb-slash">/</span><strong>{navItems.find((item) => item.id === page)?.label}</strong></div>
          <div className="topbar-right">
            <div className="today-label"><span className="today-dot" /> {new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric" }).format(new Date())}</div>
            <button className="icon-button notification-button" aria-label={`${unreadNotifications} unread notifications`} onClick={() => setPage("notifications")}><Bell size={18} />{unreadNotifications > 0 && <span />}</button>
            <button className="top-profile" onClick={signOut} aria-label="Sign out"><span className="profile-avatar small">{initials(user.full_name)}</span><ChevronDown size={15} /></button>
          </div>
        </header>

        <div className="page-content">
          {(error || success) && <div className={`notice ${error ? "notice-error" : "notice-success"}`} role={error ? "alert" : "status"}>{error || success}<button aria-label="Dismiss" onClick={() => { setError(""); setSuccess(""); }}><X size={16} /></button></div>}
          {page === "overview" && <Overview
            name={displayName} role={user.role} pets={pets} tasks={tasks} data={dashboard} petById={petById}
            onAddPet={() => setPetFormOpen(true)} onAddTask={() => setTaskFormOpen(true)}
            onComplete={completeTask} onOpenPets={() => setPage("pets")} onOpenCare={() => setPage("care")}
            onEmergency={() => setPage("emergency")} onOpenProvider={() => setPage("provider")}
            onOpenAdmin={() => setPage("administration")} onOpenVerification={() => setPage("verification")}
          />}
          {page === "pets" && <PetsPage pets={pets} selectedPet={activePet} records={records} onSelect={setSelectedPet} onAdd={() => setPetFormOpen(true)} onEdit={(pet) => setPetToEdit(pet)} onArchive={archivePet} onAddRecord={() => setRecordFormOpen(true)} />}
          {page === "care" && <CarePage tasks={tasks} petById={petById} onAdd={() => setTaskFormOpen(true)} onComplete={completeTask} />}
          {page === "records" && <RecordsPage pets={pets} selectedPet={activePet} records={records} onSelect={setSelectedPet} onAdd={() => setRecordFormOpen(true)} />}
          {page === "assistant" && <AssistantPage />}
          {page === "verification" && <VerificationPage role={user.role} onSuccess={notifySuccess} onError={notifyError} />}
          {page === "administration" && user.role === "admin" && <AdministrationPage onSuccess={notifySuccess} onError={notifyError} />}
          {page === "discover" && user.role === "owner" && <ProviderSearchPage pets={pets} onSuccess={notifySuccess} onError={notifyError} />}
          {page === "provider" && (user.role === "veterinarian" || user.role === "groomer") && <ProviderWorkspace role={user.role} onSuccess={notifySuccess} onError={notifyError} />}
          {page === "emergency" && ["owner", "volunteer", "admin"].includes(user.role) && <EmergencyPage role={user.role} pets={pets} onSuccess={notifySuccess} onError={notifyError} />}
          {page === "community" && <CommunityPage role={user.role} userId={user.id} pets={pets} onSuccess={notifySuccess} onError={notifyError} />}
          {page === "messages" && <MessagesPage userId={user.id} role={user.role} onError={notifyError} />}
          {page === "notifications" && <NotificationsPage onUnreadCount={setUnreadNotifications} onError={notifyError} />}
        </div>
      </main>

      {(petFormOpen || petToEdit) && <Modal title={petToEdit ? `Update ${petToEdit.name}'s details` : "Add a pet to your family"} onClose={() => { setPetFormOpen(false); setPetToEdit(null); }}><form className="modal-form" onSubmit={submitPet}>
        <label>Pet's name<input name="name" required maxLength={80} defaultValue={petToEdit?.name ?? ""} placeholder="e.g. Bruno" /></label>
        <div className="form-grid"><label>Species<input name="species" required maxLength={40} defaultValue={petToEdit?.species ?? ""} placeholder="Dog, cat, rabbit…" /></label><label>Breed <span className="optional">optional</span><input name="breed" maxLength={80} defaultValue={petToEdit?.breed ?? ""} placeholder="e.g. Beagle" /></label></div>
        <div className="form-grid"><label>Weight in kilograms <span className="optional">optional</span><input name="weight" type="number" min="0.1" max="500" step="0.1" defaultValue={petToEdit?.weight_kg ?? ""} placeholder="12.5" /></label><label>Birthday <span className="optional">optional</span><input name="birth_date" type="date" defaultValue={petToEdit?.birth_date ?? ""} /></label></div>
        <div className="form-grid"><label>Sex <span className="optional">optional</span><select name="sex" defaultValue={petToEdit?.sex ?? ""}><option value="">Not specified</option><option value="female">Female</option><option value="male">Male</option><option value="unknown">Unknown</option></select></label><label>Allergies <span className="optional">optional</span><input name="allergies" maxLength={2000} defaultValue={petToEdit?.allergies ?? ""} placeholder="Anything to keep in mind?" /></label></div>
        <label>Care notes <span className="optional">optional</span><textarea name="notes" maxLength={4000} rows={3} defaultValue={petToEdit?.notes ?? ""} placeholder="Favorite routines, useful details…" /></label>
        <button className="button button-primary button-full" type="submit">{petToEdit ? "Save changes" : "Save pet profile"} <ArrowRightIcon /></button>
      </form></Modal>}
      {taskFormOpen && <Modal title="Plan a care reminder" onClose={() => setTaskFormOpen(false)}><form className="modal-form" onSubmit={submitTask}>
        <label>What needs doing?<input name="title" required maxLength={160} placeholder="e.g. Evening walk" /></label>
        <div className="form-grid"><label>For which pet?<select name="pet_id" required defaultValue={pets[0]?.id ?? ""}>{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select></label><label>Type<select name="category" defaultValue="care"><option value="care">Everyday care</option><option value="vet">Vet visit</option><option value="vaccination">Vaccination</option><option value="medication">Medication</option><option value="feeding">Feeding</option><option value="grooming">Grooming</option><option value="activity">Activity</option></select></label></div>
        <label>Instructions <span className="optional">optional · e.g. medication dose</span><input name="instructions" maxLength={500} placeholder="Dose, vaccine name, or care details" /></label>
        <label>Date and time<input name="due_at" type="datetime-local" required /></label>
        <div className="form-grid"><label>Repeat<select name="repeat_interval_minutes" defaultValue=""><option value="">One-time</option><option value="720">Every 12 hours</option><option value="1440">Daily</option><option value="10080">Weekly</option><option value="43200">Every 30 days</option><option value="525600">Every 365 days</option></select></label><label>Email reminder<select name="reminder_days_before" defaultValue="1"><option value="0">On the due date</option><option value="1">1 day before</option><option value="3">3 days before</option><option value="7">7 days before</option></select></label></div>
        <button className="button button-primary button-full" type="submit">Save reminder <ArrowRightIcon /></button>
      </form></Modal>}
      {recordFormOpen && <Modal title="Add a health note" onClose={() => setRecordFormOpen(false)}><form className="modal-form" onSubmit={submitRecord}>
        <p className="form-disclaimer">This will be saved as an owner observation, not a veterinary diagnosis.</p>
        <label>Note type<select name="record_type" defaultValue="observation"><option value="observation">Owner observation</option><option value="vaccination">Vaccination note</option><option value="visit">Vet visit summary</option><option value="allergy">Allergy</option><option value="medication">Medication note</option></select></label>
        <label>Title<input name="title" required maxLength={160} placeholder="e.g. New food introduced" /></label>
        <label>Details<textarea name="details" required maxLength={4000} rows={4} placeholder="Add useful details…" /></label>
        <button className="button button-primary button-full" type="submit">Save health note <ArrowRightIcon /></button>
      </form></Modal>}
    </div>
  );
}

function ArrowRightIcon() {
  return <span aria-hidden="true">→</span>;
}

function Overview({ name, role, pets, tasks, data, petById, onAddPet, onAddTask, onComplete, onOpenPets, onOpenCare, onEmergency, onOpenProvider, onOpenAdmin, onOpenVerification }: {
  name: string; role: string; pets: Pet[]; tasks: CareTask[]; data: DashboardData | null; petById: Map<number, Pet>;
  onAddPet: () => void; onAddTask: () => void; onComplete: (task: CareTask) => void;
  onOpenPets: () => void; onOpenCare: () => void; onEmergency: () => void;
  onOpenProvider: () => void; onOpenAdmin: () => void; onOpenVerification: () => void;
}) {
  const upcoming = tasks.filter((task) => !task.completed).slice(0, 4);
  if (role !== "owner") {
    const isProvider = role === "veterinarian" || role === "groomer";
    const isVolunteer = role === "volunteer";
    const isAdmin = role === "admin";
    const roleName = isProvider ? (role === "veterinarian" ? "Veterinarian" : "Groomer") : isVolunteer ? "Volunteer" : isAdmin ? "Administrator" : "Shelter";
    const firstMetric = isProvider
      ? { label: "Pending appointments", value: data?.pending_appointments ?? 0, icon: <CalendarDays size={18} /> }
      : isVolunteer
        ? { label: "Active assignments", value: data?.active_emergencies ?? 0, icon: <ShieldAlert size={18} /> }
        : isAdmin
          ? { label: "Applications to review", value: data?.pending_applications ?? 0, icon: <BadgeCheck size={18} /> }
          : { label: "Your role", value: 1, icon: <Heart size={18} /> };
    const secondMetric = isProvider
      ? { label: "Open appointments", value: data?.active_appointments ?? 0, icon: <Clock3 size={18} /> }
      : isAdmin
        ? { label: "Suspended accounts", value: data?.suspended_users ?? 0, icon: <ShieldCheck size={18} /> }
        : { label: "Account status", value: 1, icon: <Check size={18} /> };
    const action = isProvider
      ? { label: "Open provider workspace", onClick: onOpenProvider }
      : isVolunteer
        ? { label: "View emergency requests", onClick: onEmergency }
        : isAdmin
          ? { label: "Review applications", onClick: onOpenAdmin }
          : { label: "View access status", onClick: onOpenVerification };
    return <>
      <section className="welcome-row">
        <div><span className="page-kicker">{roleName.toUpperCase()} WORKSPACE</span><h1>Welcome, {name}<span className="heading-wave">✳</span></h1><p>Your PetVerse workspace is ready for you.</p></div>
        <button className="button button-soft" onClick={action.onClick}>{action.label} <ArrowRight size={16} /></button>
      </section>
      <section className="stats-grid role-stats-grid">
        <StatCard icon={firstMetric.icon} tone="mint" label={firstMetric.label} value={firstMetric.value} note="Updated from your workspace" />
        <StatCard icon={secondMetric.icon} tone="lavender" label={secondMetric.label} value={secondMetric.value} note="Visible to your account only" />
      </section>
      <section className="content-card role-dashboard-card">
        <span className="section-kicker">YOUR WORKSPACE</span>
        <h2>{isProvider ? "Care appointments, thoughtfully managed." : isVolunteer ? "Community support, coordinated safely." : isAdmin ? "Review and account oversight." : "Your shelter workspace."}</h2>
        <p>{isProvider ? "Manage your profile, availability, and appointment requests from the provider workspace." : isVolunteer ? "Check your emergency queue and update the status of assignments you have accepted." : isAdmin ? "Review professional access requests and manage account status." : "Additional shelter tools will appear here as they become available."}</p>
        <button className="text-link" onClick={action.onClick}>{action.label} <span>→</span></button>
      </section>
    </>;
  }
  return <>
    <section className="welcome-row">
      <div><span className="page-kicker">{new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date()).toUpperCase()}</span><h1>Good things ahead, {name}<span className="heading-wave">✳</span></h1><p>Here's a little look at the care you share.</p></div>
      <button className="button button-soft" onClick={onAddTask}><Plus size={17} /> Add a reminder</button>
    </section>
    <section className="hero-card">
      <div className="hero-copy"><span className="hero-label"><Sparkles size={14} /> YOUR DAILY PAUSE</span><h2>Little moments<br />make a <em>big</em> difference.</h2><p>Every walk, check-in, and cuddle adds up to a life well loved.</p><button className="hero-link" onClick={onOpenCare}>See your care calendar <span>→</span></button></div>
      <div className="hero-art"><div className="sun-disc" /><div className="leaf-shape leaf-one" /><div className="leaf-shape leaf-two" /><div className="hero-pet">🐕</div><div className="hero-heart">♡</div><div className="hero-sparkle">✦</div></div>
      <div className="hero-caption">A softer rhythm, together.</div>
    </section>
    <section className="stats-grid">
      <StatCard icon={<PawPrint size={18} />} tone="mint" label="Pets in your care" value={data?.pet_count ?? pets.length} note="Every one, a whole world" />
      <StatCard icon={<Clock3 size={18} />} tone="peach" label="Coming up" value={data?.due_tasks ?? upcoming.length} note={upcoming.length ? "Care moments to look forward to" : "A little room to breathe"} />
      <StatCard icon={<Check size={18} />} tone="lavender" label="Done with love" value={data?.completed_tasks ?? 0} note="Small wins count, too" />
      <StatCard icon={<FileHeart size={18} />} tone="blue" label="Health notes" value={data?.recent_records ?? 0} note="Little details, thoughtfully kept" />
    </section>
    <section className="dashboard-grid">
      <div className="content-card upcoming-card">
        <div className="section-title-row"><div><span className="section-kicker">AHEAD IN YOUR DAY</span><h2>Care, coming up</h2></div><button className="text-link" onClick={onOpenCare}>View calendar <span>→</span></button></div>
        {upcoming.length ? <div className="task-list">{upcoming.map((task) => <TaskRow key={task.id} task={task} petName={petById.get(task.pet_id)?.name ?? "Your pet"} onComplete={onComplete} />)}</div> : <EmptyState icon={<CalendarDays size={19} />} title="Your calendar has room to breathe" text="Add a gentle reminder for the next little thing." action="Add a reminder" onClick={onAddTask} />}
      </div>
      <div className="content-card pets-card">
        <div className="section-title-row"><div><span className="section-kicker">YOUR LITTLE CREW</span><h2>My pets <span className="count-pill">{pets.length}</span></h2></div><button className="text-link" onClick={onOpenPets}>All pets <span>→</span></button></div>
        {pets.length ? <div className="mini-pet-list">{pets.slice(0, 3).map((pet, index) => <PetMiniCard key={pet.id} pet={pet} index={index} />)}</div> : <EmptyState icon={<PawPrint size={19} />} title="Every care story starts somewhere" text="Add your first pet and make this space yours." action="Add a pet" onClick={onAddPet} />}
      </div>
    </section>
    <button className="emergency-strip" onClick={onEmergency}><span className="emergency-icon"><ShieldAlert size={19} /></span><span><strong>Need urgent help?</strong><small>See immediate safety guidance and optional volunteer coordination.</small></span><span className="emergency-arrow">→</span></button>
  </>;
}

function StatCard({ icon, tone, label, value, note }: { icon: ReactNode; tone: string; label: string; value: number; note: string }) {
  return <article className="stat-card"><span className={`stat-icon ${tone}`}>{icon}</span><span className="stat-label">{label}</span><strong className="stat-value">{value}</strong><span className="stat-note">{note}</span><div className={`stat-swoosh ${tone}`} /></article>;
}

function TaskRow({ task, petName, onComplete }: { task: CareTask; petName: string; onComplete: (task: CareTask) => void }) {
  const repeatLabel = task.repeat_interval_minutes === 720 ? "Every 12 hours"
    : task.repeat_interval_minutes === 1440 ? "Daily"
      : task.repeat_interval_minutes === 10080 ? "Weekly"
        : task.repeat_interval_minutes === 43200 ? "Every 30 days"
          : task.repeat_interval_minutes === 525600 ? "Yearly" : null;
  return <div className="task-row"><button className="task-check" aria-label={`Complete ${task.title}`} onClick={() => onComplete(task)}><Check size={13} /></button><div className="task-main"><strong>{task.title}</strong><span>{petName} <i /> {task.category}{task.instructions ? ` · ${task.instructions}` : ""}{repeatLabel ? ` · ${repeatLabel}` : ""}</span></div><span className="task-time">{formatDate(task.due_at)}</span></div>;
}

function PetMiniCard({ pet, index }: { pet: Pet; index: number }) {
  return <article className="mini-pet-card"><div className={`pet-portrait portrait-${index % 4}`}>{pet.photo_url ? <img src={pet.photo_url} alt="" /> : <span>{pet.species.toLowerCase().includes("cat") ? "🐱" : pet.species.toLowerCase().includes("bird") ? "🐦" : "🐶"}</span>}</div><div className="mini-pet-info"><strong>{pet.name}</strong><span>{pet.breed || pet.species}{pet.weight_kg ? ` · ${pet.weight_kg} kg` : ""}</span></div><span className="pet-health-dot" title="Profile active" /></article>;
}

function PetsPage({ pets, selectedPet, records, onSelect, onAdd, onEdit, onArchive, onAddRecord }: {
  pets: Pet[]; selectedPet?: Pet; records: MedicalRecord[]; onSelect: (id: number) => void;
  onAdd: () => void; onEdit: (pet: Pet) => void; onArchive: (pet: Pet) => void; onAddRecord: () => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = pets.filter((pet) => `${pet.name} ${pet.species} ${pet.breed ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  return <>
    <PageHeading kicker="THE HEART OF YOUR HOME" title="Your pets" subtitle="Every detail helps make their care a little more personal." action={<button className="button button-primary" onClick={onAdd}><Plus size={17} /> Add a pet</button>} />
    <div className="pet-page-layout">
      <div className="pet-list-panel">
        <div className="search-box"><Search size={17} /><input aria-label="Search pets" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a pet…" /></div>
        {filtered.length ? filtered.map((pet, index) => <button key={pet.id} className={`pet-select-card ${selectedPet?.id === pet.id ? "chosen" : ""}`} onClick={() => onSelect(pet.id)}><span className={`pet-portrait portrait-${index % 4}`}>{pet.species.toLowerCase().includes("cat") ? "🐱" : pet.species.toLowerCase().includes("bird") ? "🐦" : "🐶"}</span><span className="pet-select-info"><strong>{pet.name}</strong><small>{pet.breed || pet.species}</small></span><span className="select-chevron">→</span></button>) : <div className="empty-inline">No pets match that search.</div>}
      </div>
      <div className="pet-detail-panel">
        {selectedPet ? <>
          <div className="pet-detail-header"><div className="pet-detail-avatar">{selectedPet.species.toLowerCase().includes("cat") ? "🐱" : "🐶"}</div><div><span className="section-kicker">A LITTLE ABOUT</span><h2>{selectedPet.name}</h2><p>{selectedPet.breed || selectedPet.species}</p></div><button className="quiet-button archive-button" onClick={() => onEdit(selectedPet)}>Edit details</button><button className="quiet-button" onClick={() => onArchive(selectedPet)}>Archive</button></div>
          <div className="pet-facts"><Fact label="Species" value={selectedPet.species} /><Fact label="Breed" value={selectedPet.breed || "Not added"} /><Fact label="Weight" value={selectedPet.weight_kg ? `${selectedPet.weight_kg} kg` : "Not added"} /><Fact label="Birthday" value={selectedPet.birth_date ? formatDate(selectedPet.birth_date) : "Not added"} /></div>
          <div className="detail-block"><div className="section-title-row"><div><span className="section-kicker">JUST FOR THEM</span><h3>Care notes</h3></div></div><p className="detail-copy">{selectedPet.notes || "Add the little things that help everyone care for your pet, from favorite games to daily routines."}</p>{selectedPet.allergies && <div className="allergy-note"><strong>Allergies to remember</strong><span>{selectedPet.allergies}</span></div>}</div>
          <div className="detail-block"><div className="section-title-row"><div><span className="section-kicker">THEIR WELLNESS STORY</span><h3>Recent health notes</h3></div><button className="text-link" onClick={onAddRecord}><Plus size={15} /> Add note</button></div>{records.length ? <div className="record-list">{records.slice(0, 4).map((record) => <div className="record-row" key={record.id}><span className="record-marker"><FileHeart size={16} /></span><div><strong>{record.title}</strong><small>{record.record_type} · {formatDate(record.recorded_at)}</small></div><span className="owner-note-badge">Owner note</span></div>)}</div> : <p className="detail-copy">No health notes just yet. Keep important observations together in one place.</p>}</div>
        </> : <EmptyState icon={<PawPrint size={21} />} title="Meet your care crew" text="Add a pet to create their own space for care details and wellness notes." action="Add a pet" onClick={onAdd} />}
      </div>
    </div>
  </>;
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div className="fact-item"><span>{label}</span><strong>{value}</strong></div>;
}

function CarePage({ tasks, petById, onAdd, onComplete }: { tasks: CareTask[]; petById: Map<number, Pet>; onAdd: () => void; onComplete: (task: CareTask) => void }) {
  const open = tasks.filter((task) => !task.completed);
  const done = tasks.filter((task) => task.completed);
  return <>
    <PageHeading kicker="A GENTLE NUDGE" title="Care calendar" subtitle="A rhythm for the little things that keep them feeling their best." action={<button className="button button-primary" onClick={onAdd}><Plus size={17} /> Add reminder</button>} />
    <div className="calendar-summary"><div><span className="calendar-icon"><CalendarDays size={20} /></span><span><strong>{open.length} things on your list</strong><small>One thoughtful moment at a time.</small></span></div><div className="summary-complete"><Check size={15} /> {done.length} done</div></div>
    <section className="content-card care-list-card"><div className="section-title-row"><div><span className="section-kicker">UP NEXT</span><h2>Coming up</h2></div></div>{open.length ? <div className="task-list">{open.map((task) => <TaskRow key={task.id} task={task} petName={petById.get(task.pet_id)?.name ?? "Your pet"} onComplete={onComplete} />)}</div> : <EmptyState icon={<Check size={20} />} title="All caught up for now" text="Enjoy the breathing room. You can add a reminder any time." action="Plan a reminder" onClick={onAdd} />}</section>
    {done.length > 0 && <section className="content-card care-list-card completed-card"><div className="section-title-row"><div><span className="section-kicker">LOOK AT YOU GO</span><h2>Recently completed</h2></div></div><div className="task-list">{done.slice(0, 8).map((task) => <div className="task-row task-done" key={task.id}><span className="task-complete-icon"><Check size={14} /></span><div className="task-main"><strong>{task.title}</strong><span>{petById.get(task.pet_id)?.name ?? "Your pet"} <i /> {task.category}</span></div><span className="task-time">Done</span></div>)}</div></section>}
  </>;
}

function RecordsPage({ pets, selectedPet, records, onSelect, onAdd }: { pets: Pet[]; selectedPet?: Pet; records: MedicalRecord[]; onSelect: (id: number) => void; onAdd: () => void }) {
  return <>
    <PageHeading kicker="LITTLE DETAILS, SAFELY KEPT" title="Health notes" subtitle="Keep observations and important care details together for the next visit." action={selectedPet ? <button className="button button-primary" onClick={onAdd}><Plus size={17} /> Add a note</button> : undefined} />
    <div className="record-controls"><label>Pet<select value={selectedPet?.id ?? ""} onChange={(event) => onSelect(Number(event.target.value))}>{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select></label><span className="owner-record-warning"><ShieldCheck size={15} /> Owner-entered notes are not professional veterinary records.</span></div>
    <section className="content-card records-page-card">{records.length ? <div className="record-list record-list-large">{records.map((record) => <article className="record-row" key={record.id}><span className="record-marker"><FileHeart size={16} /></span><div className="record-content"><strong>{record.title}</strong><small>{record.record_type} · {formatDate(record.recorded_at)}</small><p>{record.details}</p></div><span className="owner-note-badge">Owner note</span></article>)}</div> : <EmptyState icon={<FileHeart size={20} />} title="A thoughtful place for health notes" text={selectedPet ? `Keep observations about ${selectedPet.name} together for future visits.` : "Add a pet first, then keep their observations in one place."} action={selectedPet ? "Add a note" : "Add a pet"} onClick={selectedPet ? onAdd : undefined} />}</section>
  </>;
}

function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [species, setSpecies] = useState("");
  const [answer, setAnswer] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setAnswer("");
    setUrgent(false);
    try {
      const result = await api.askCareAssistant(question, species || undefined);
      setAnswer(result.answer);
      setUrgent(result.urgent);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to get care guidance.");
    } finally {
      setBusy(false);
    }
  }

  return <>
    <PageHeading kicker="GENTLE, GENERAL GUIDANCE" title="Care assistant" subtitle="General pet-care education, not a diagnosis or a substitute for veterinary advice." />
    <section className="assistant-card assistant-interactive">
      <span className="assistant-emblem"><Sparkles size={24} /></span>
      <div>
        <span className="section-kicker">AI-POWERED EDUCATION</span>
        <h2>What would you like to know?</h2>
        <p>Your question and optional species are sent to the configured AI provider. Pet profiles, account details, and health records are not sent.</p>
        <form className="assistant-form" onSubmit={submit}>
          <label>Pet species <span className="optional">optional</span><input value={species} onChange={(event) => setSpecies(event.target.value)} maxLength={40} placeholder="Dog, cat, rabbit…" /></label>
          <label>Your question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} required minLength={5} maxLength={2000} rows={4} placeholder="Ask about everyday care, routines, or general wellness…" /></label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="button button-primary" type="submit" disabled={busy}>{busy ? "Thinking…" : "Ask the care assistant"} <ArrowRight size={16} /></button>
        </form>
        {answer && <article className={`assistant-answer ${urgent ? "assistant-answer-urgent" : ""}`} role="status"><strong>{urgent ? "Urgent guidance" : "General guidance"}</strong><p>{answer}</p></article>}
        <div className="assistant-safety"><Stethoscope size={17} /><span>For urgent symptoms or possible poisoning, contact an emergency veterinarian now. Don’t wait for an AI response.</span></div>
      </div>
    </section>
  </>;
}

function EmergencyPage({ role, pets, onSuccess, onError }: {
  role: string; pets: Pet[]; onSuccess: (message: string) => void; onError: (message: string) => void;
}) {
  const [requests, setRequests] = useState<EmergencyRequest[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [volunteerProfile, setVolunteerProfile] = useState<VolunteerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const requestPromise = role === "volunteer" ? api.availableEmergencies() : api.emergencyRequests();
    Promise.all([
      requestPromise,
      api.notifications(),
      role === "volunteer"
        ? api.volunteerProfile().catch((reason: unknown) => {
          if (reason instanceof Error && reason.message.includes("Set your volunteer area")) return null;
          throw reason;
        })
        : Promise.resolve(null),
    ]).then(([data, alerts, profile]) => {
      if (!active) return;
      setRequests(data);
      setNotifications(alerts.filter((item) => item.kind === "emergency"));
      setVolunteerProfile(profile);
    }).catch((reason: unknown) => {
      if (active) onError(reason instanceof Error ? reason.message : "Unable to load emergency assistance.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [role, onError, refresh]);

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const petValue = String(form.get("pet_id") || "");
    try {
      await api.createEmergency({
        category: String(form.get("category")) as EmergencyCategory,
        severity: String(form.get("severity")) as "critical" | "urgent",
        description: String(form.get("description")),
        pet_id: petValue ? Number(petValue) : null,
        location: String(form.get("location")).trim() || null,
      });
      formElement.reset();
      setRefresh((value) => value + 1);
      onSuccess("Your request was submitted. Contact an emergency veterinarian directly—volunteer dispatch is not a substitute for veterinary care.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to submit your request.");
    }
  }

  async function saveVolunteerProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const profile = await api.updateVolunteerProfile({
        service_area: String(form.get("service_area")).trim() || null,
        is_available: form.get("is_available") === "on",
      });
      setVolunteerProfile(profile);
      setRefresh((value) => value + 1);
      onSuccess(profile.is_available ? "You are marked available for assistance requests." : "You are marked unavailable.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to update your volunteer settings.");
    }
  }

  async function acceptRequest(request: EmergencyRequest) {
    if (!window.confirm("Accept this request? You are a volunteer, not a substitute for a qualified veterinarian.")) return;
    try {
      await api.acceptEmergency(request.id);
      setRefresh((value) => value + 1);
      onSuccess("Request assigned to you. Coordinate with the owner and direct urgent medical needs to a veterinarian.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to accept this request.");
    }
  }

  async function declineRequest(request: EmergencyRequest) {
    try {
      await api.declineEmergency(request.id);
      setRefresh((value) => value + 1);
      onSuccess("Request declined; it remains available to other eligible volunteers.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to decline this request.");
    }
  }

  async function updateStatus(request: EmergencyRequest, status: "responding" | "in_progress" | "completed" | "cancelled" | "escalated") {
    if (status === "cancelled" && !window.confirm("Cancel this assistance request?")) return;
    try {
      await api.updateEmergencyStatus(request.id, status);
      setRefresh((value) => value + 1);
      onSuccess(`Request status updated to ${status.replace("_", " ")}.`);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to update this request.");
    }
  }

  async function markRead(notification: AppNotification) {
    try {
      await api.markNotificationRead(notification.id);
      setNotifications((current) => current.map((item) => item.id === notification.id ? { ...item, is_read: true } : item));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to mark notification as read.");
    }
  }

  const canSubmit = role === "owner";
  const canVolunteer = role === "volunteer";
  const isAdmin = role === "admin";

  return <>
    <PageHeading kicker="URGENT SAFETY FIRST" title="Emergency assistance" subtitle="Immediate professional care comes first. Volunteer coordination is optional and may not be available." />
    <section className="emergency-critical-banner" role="alert"><span><ShieldAlert size={22} /></span><div><strong>Is your pet having trouble breathing, bleeding heavily, seizing, badly injured, or possibly poisoned?</strong><p>Contact a local emergency veterinarian or animal poison service now. Do not wait for a volunteer or this website. Follow a veterinary professional’s instructions and do not induce vomiting unless directed.</p></div></section>
    <div className="emergency-external-note"><Stethoscope size={16} /><span>PetVerse does not provide emergency medical advice, contact emergency services for you, or guarantee volunteer availability or arrival.</span></div>
    {canSubmit && <section className="emergency-columns">
      <div className="content-card emergency-form-card"><div className="section-title-row"><div><span className="section-kicker">OPTIONAL COMMUNITY REQUEST</span><h2>Request assistance</h2></div></div><p className="detail-copy">Send a concise request after reviewing the urgent guidance above. Sharing location is optional; only you, an assigned volunteer, and authorized administrators can view it.</p>
        <form className="modal-form emergency-form" onSubmit={submitRequest}>
          <div className="form-grid"><label>Situation<select name="category" required defaultValue="other"><option value="breathing_difficulty">Breathing difficulty</option><option value="suspected_poisoning">Suspected poisoning</option><option value="serious_injury">Serious injury</option><option value="severe_bleeding">Severe bleeding</option><option value="seizure">Seizure</option><option value="heat_emergency">Heat-related emergency</option><option value="road_accident">Road accident</option><option value="missing_pet">Missing pet</option><option value="injured_stray">Injured stray animal</option><option value="other">Other urgent situation</option></select></label><label>Urgency<select name="severity" defaultValue="urgent"><option value="critical">Critical — seeking veterinary care now</option><option value="urgent">Urgent — prompt help needed</option></select></label></div>
          <label>Pet <span className="optional">optional for strays</span><select name="pet_id" defaultValue=""><option value="">No linked pet</option>{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select></label>
          <label>What help is needed?<textarea name="description" required minLength={5} maxLength={4000} rows={4} placeholder="Share essential details for a volunteer. This is not a substitute for a veterinary examination." /></label>
          <label>Approximate location <span className="optional">optional</span><input name="location" maxLength={400} placeholder="Area or nearby landmark—avoid home access details" /></label>
          <button className="button button-primary button-full" type="submit"><ShieldAlert size={16} /> Submit assistance request</button>
        </form>
      </div>
      <div className="content-card"><span className="section-kicker">YOUR REQUESTS</span><h2 className="emergency-section-heading">Updates</h2>{loading ? <p className="detail-copy">Loading requests…</p> : requests.length ? <EmergencyRequestList requests={requests} role={role} onUpdate={updateStatus} /> : <EmptyState icon={<ShieldAlert size={19} />} title="No assistance requests" text="If you need community assistance after contacting a veterinarian, you can submit a request here." />}</div>
    </section>}
    {canVolunteer && <section className="emergency-volunteer-layout">
      <div className="content-card"><div className="section-title-row"><div><span className="section-kicker">VOLUNTEER AVAILABILITY</span><h2>Set your response area</h2></div></div><p className="detail-copy">Volunteers help coordinate community assistance and are not veterinary professionals unless separately qualified. Do not accept requests outside your capacity.</p><form className="modal-form emergency-form" onSubmit={saveVolunteerProfile}><label>Area you can serve<input name="service_area" maxLength={160} defaultValue={volunteerProfile?.service_area ?? ""} placeholder="City, district, or neighborhood" /></label><label className="availability-check"><input name="is_available" type="checkbox" defaultChecked={volunteerProfile?.is_available ?? false} /><span>I'm currently available to see eligible requests</span></label><button className="button button-primary" type="submit">Save availability</button></form></div>
      <div className="content-card"><div className="section-title-row"><div><span className="section-kicker">COMMUNITY REQUESTS</span><h2>Available to help</h2></div></div>{loading ? <p className="detail-copy">Loading requests…</p> : requests.length ? <EmergencyRequestList requests={requests} role={role} onAccept={acceptRequest} onDecline={declineRequest} onUpdate={updateStatus} /> : <EmptyState icon={<ShieldCheck size={19} />} title={volunteerProfile?.is_available ? "No eligible requests right now" : "Mark yourself available first"} text="Requests are community submissions and volunteer coverage is not guaranteed." />}</div>
    </section>}
    {isAdmin && <section className="content-card admin-section"><div className="section-title-row"><div><span className="section-kicker">ADMIN OVERSIGHT</span><h2>Assistance requests</h2></div></div>{loading ? <p className="detail-copy">Loading requests…</p> : requests.length ? <EmergencyRequestList requests={requests} role={role} onUpdate={updateStatus} /> : <EmptyState icon={<ShieldAlert size={19} />} title="No assistance requests" text="Submitted requests appear here for oversight." />}</section>}
    {role === "owner" || role === "volunteer" ? <section className="content-card admin-section emergency-alerts"><div className="section-title-row"><div><span className="section-kicker">PRIVATE IN-APP UPDATES</span><h2>Emergency notifications <span className="count-pill">{notifications.filter((item) => !item.is_read).length}</span></h2></div></div>{notifications.length ? notifications.slice(0, 8).map((notification) => <article className={`emergency-notification ${notification.is_read ? "" : "unread"}`} key={notification.id}><span>{notification.message}</span>{!notification.is_read && <button className="text-link" onClick={() => void markRead(notification)}>Mark read</button>}</article>) : <p className="detail-copy">Status updates for your emergency requests will appear here. Email and push delivery are not configured.</p>}</section> : null}
  </>;
}

function EmergencyRequestList({ requests, role, onAccept, onDecline, onUpdate }: {
  requests: EmergencyRequest[];
  role: string;
  onAccept?: (request: EmergencyRequest) => void;
  onDecline?: (request: EmergencyRequest) => void;
  onUpdate: (request: EmergencyRequest, status: "responding" | "in_progress" | "completed" | "cancelled" | "escalated") => void;
}) {
  return <div className="emergency-request-list">{requests.map((request) => <article className="emergency-request-card" key={request.id}>
    <div className="emergency-request-header"><span className={`urgency-pill ${request.severity}`}>{request.severity}</span><span className={`request-status status-${request.status}`}>{request.status.replace("_", " ")}</span></div>
    <strong>{emergencyCategoryLabel(request.category)}</strong><p>{request.description}</p>
    <div className="emergency-request-meta">{request.pet_id ? `Pet #${request.pet_id}` : "No linked pet"} · {formatDate(request.created_at)}{request.location && <span> · {request.location}</span>}</div>
    {request.assigned_volunteer_id && <div className="emergency-assigned-note">{role === "owner" ? "A verified volunteer has accepted this request." : `Assigned volunteer account #${request.assigned_volunteer_id}`}</div>}
    <div className="emergency-request-actions">
      {role === "volunteer" && request.status === "submitted" && onAccept && <button className="button button-soft" onClick={() => onAccept(request)}>Accept request</button>}
      {role === "volunteer" && request.status === "submitted" && onDecline && <button className="quiet-button" onClick={() => onDecline(request)}>Decline</button>}
      {role === "volunteer" && request.status === "assigned" && <button className="quiet-button" onClick={() => onUpdate(request, "responding")}>I'm responding</button>}
      {role === "volunteer" && request.status === "responding" && <button className="quiet-button" onClick={() => onUpdate(request, "in_progress")}>Assistance started</button>}
      {role === "volunteer" && ["responding", "in_progress"].includes(request.status) && <button className="quiet-button" onClick={() => onUpdate(request, "completed")}>Complete</button>}
      {role === "volunteer" && ["assigned", "responding", "in_progress"].includes(request.status) && <button className="quiet-button" onClick={() => onUpdate(request, "escalated")}>Escalate</button>}
      {role === "owner" && ["submitted", "assigned", "responding", "in_progress"].includes(request.status) && <><button className="quiet-button" onClick={() => onUpdate(request, "escalated")}>Escalate</button><button className="quiet-button" onClick={() => onUpdate(request, "cancelled")}>Cancel</button></>}
    </div>
  </article>)}</div>;
}

function MessagesPage({ userId, role, onError }: {
  userId: number; role: string; onError: (message: string) => void;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [emergencies, setEmergencies] = useState<EmergencyRequest[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [sending, setSending] = useState(false);

  const loadConversations = useCallback(async () => {
    try {
      const result = await api.conversations();
      setConversations(result);
      setSelected((current) => current ? result.find((item) => item.id === current.id) ?? null : null);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to load conversations.");
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const appointmentsPromise = ["owner", "veterinarian", "groomer"].includes(role)
      ? api.appointments().catch((reason: unknown) => {
        if (reason instanceof Error && reason.message.includes("403")) return [];
        throw reason;
      })
      : Promise.resolve([]);
    const emergenciesPromise = ["owner", "volunteer"].includes(role)
      ? (role === "owner" ? api.emergencyRequests() : api.availableEmergencies())
      : Promise.resolve([]);
    Promise.all([api.conversations(), appointmentsPromise, emergenciesPromise]).then(([threads, bookings, requests]) => {
      if (!active) return;
      setConversations(threads);
      setAppointments(bookings);
      setEmergencies(requests);
      setSelected((current) => current ? threads.find((item) => item.id === current.id) ?? null : null);
    }).catch((reason: unknown) => {
      if (active) onError(reason instanceof Error ? reason.message : "Unable to load messaging.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [role, onError, refresh]);

  useEffect(() => {
    let active = true;
    if (!selected) {
      setMessages([]);
      return;
    }
    api.messages(selected.id).then((items) => {
      if (active) {
        setMessages(items);
        setConversations((current) => current.map((item) =>
          item.id === selected.id ? { ...item, unread_count: 0 } : item,
        ));
      }
    }).catch((reason: unknown) => {
      if (active) onError(reason instanceof Error ? reason.message : "Unable to load messages.");
    });
    return () => { active = false; };
  }, [selected?.id, onError, refresh]);

  async function openContext(contextType: "appointment" | "emergency", contextId: number) {
    try {
      const conversation = await api.openConversation(contextType, contextId);
      setConversations((current) => [conversation, ...current.filter((item) => item.id !== conversation.id)]);
      setSelected(conversation);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to open this conversation.");
    }
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !draft.trim()) return;
    setSending(true);
    try {
      const message = await api.sendMessage(selected.id, draft);
      setMessages((current) => [...current, message]);
      setDraft("");
      await loadConversations();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to send this message.");
    } finally {
      setSending(false);
    }
  }

  const openAppointments = appointments.filter((appointment) => !["cancelled", "rejected"].includes(appointment.status));
  const assignedEmergencies = emergencies.filter((request) =>
    request.assigned_volunteer_id !== null
    && ["assigned", "responding", "in_progress", "completed", "escalated"].includes(request.status),
  );

  return <>
    <PageHeading kicker="PRIVATE, CONTEXT-LINKED CHAT" title="Messages" subtitle="Only the appointment participants or an emergency request's owner and assigned volunteer can open its conversation." action={<button className="quiet-button" onClick={() => setRefresh((value) => value + 1)}>Refresh</button>} />
    <section className="messages-layout">
      <aside className="messages-sidebar content-card">
        <span className="section-kicker">YOUR CONVERSATIONS</span>
        {loading ? <p className="detail-copy">Loading conversations…</p> : conversations.length ? conversations.map((conversation) => <button key={conversation.id} className={`conversation-item ${selected?.id === conversation.id ? "conversation-selected" : ""}`} onClick={() => setSelected(conversation)}><span className="conversation-avatar"><MessageCircle size={17} /></span><span className="conversation-copy"><strong>{conversation.other_user_name}</strong><small>{conversation.appointment_id ? `Appointment #${conversation.appointment_id}` : `Emergency #${conversation.emergency_request_id}`}</small><span>{conversation.last_message || "No messages yet"}</span></span>{conversation.unread_count > 0 && <span className="unread-pill">{conversation.unread_count}</span>}</button>) : <EmptyState icon={<MessageCircle size={19} />} title="No conversations yet" text="Open a conversation from an appointment or assigned emergency request." />}
        {openAppointments.length > 0 && <div className="context-links"><span className="section-kicker">APPOINTMENTS</span>{openAppointments.slice(0, 8).map((appointment) => <button key={appointment.id} onClick={() => void openContext("appointment", appointment.id)}><span>{appointment.service_kind} · {formatDate(appointment.starts_at)}</span><small>{appointment.status} · #{appointment.id}</small></button>)}</div>}
        {assignedEmergencies.length > 0 && <div className="context-links"><span className="section-kicker">ASSIGNED ASSISTANCE</span>{assignedEmergencies.slice(0, 8).map((request) => <button key={request.id} onClick={() => void openContext("emergency", request.id)}><span>{emergencyCategoryLabel(request.category)}</span><small>{request.status.replace("_", " ")} · #{request.id}</small></button>)}</div>}
      </aside>
      <section className="content-card chat-panel">
        {selected ? <>
          <header className="chat-header"><span className="conversation-avatar"><MessageCircle size={17} /></span><span><strong>{selected.other_user_name}</strong><small>{selected.appointment_id ? `Appointment #${selected.appointment_id}` : `Emergency #${selected.emergency_request_id}`}</small></span><button className="quiet-button" onClick={() => setRefresh((value) => value + 1)}>Refresh messages</button></header>
          <div className="chat-safety-note"><ShieldCheck size={14} /> Keep personal and sensitive information to a minimum. Chat is not monitored for emergencies.</div>
          <div className="chat-messages">{messages.length ? messages.map((message) => <article className={`chat-bubble ${message.sender_id === userId ? "mine" : ""}`} key={message.id}><span className="chat-sender">{message.sender_id === userId ? "You" : message.sender_name}</span><p>{message.body}</p><time>{new Date(message.created_at).toLocaleString()}</time></article>) : <EmptyState icon={<MessageCircle size={19} />} title="A new conversation" text="Messages are saved to this linked appointment or assigned assistance request." />}</div>
          <form className="chat-compose" onSubmit={submitMessage}><textarea aria-label="Message" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={4000} rows={2} placeholder="Write a message…" /><button className="button button-primary" type="submit" disabled={sending || !draft.trim()}>{sending ? "Sending…" : "Send"} <Send size={15} /></button></form>
        </> : <EmptyState icon={<MessageCircle size={20} />} title="Choose a conversation" text="Select an existing conversation or open one from an appointment or assigned assistance request." />}
      </section>
    </section>
    <p className="messaging-limitation">Messages use authenticated HTTP requests and refresh on demand; WebSocket/live updates, attachments, blocking, and reporting are not available yet.</p>
  </>;
}

function NotificationsPage({ onUnreadCount, onError }: {
  onUnreadCount: (count: number) => void; onError: (message: string) => void;
}) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    api.notifications().then((notifications) => {
      if (active) {
        setItems(notifications);
        onUnreadCount(notifications.filter((item) => !item.is_read).length);
      }
    }).catch((reason: unknown) => {
      if (active) onError(reason instanceof Error ? reason.message : "Unable to load notifications.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [onError, onUnreadCount, refresh]);

  async function markRead(item: AppNotification) {
    try {
      await api.markNotificationRead(item.id);
      setItems((current) => current.map((notification) =>
        notification.id === item.id ? { ...notification, is_read: true } : notification,
      ));
      onUnreadCount(Math.max(0, items.filter((notification) => !notification.is_read).length - 1));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to mark notification as read.");
    }
  }

  return <>
    <PageHeading kicker="YOUR PRIVATE UPDATES" title="Notifications" subtitle="In-app updates for messages and emergency request status. External delivery is not configured." action={<button className="quiet-button" onClick={() => setRefresh((value) => value + 1)}>Refresh</button>} />
    <section className="content-card notifications-page">{loading ? <p className="detail-copy">Loading notifications…</p> : items.length ? items.map((item) => <article className={`notification-row ${item.is_read ? "" : "notification-unread"}`} key={item.id}><span className={`notification-kind-icon ${item.kind}`} title={item.kind}>{item.kind === "message" ? <MessageCircle size={16} /> : <Bell size={16} />}</span><div className="notification-content"><strong>{item.kind === "message" ? "New message" : "Care update"}</strong><p>{item.message}</p><small>{new Date(item.created_at).toLocaleString()}</small></div>{!item.is_read && <button className="text-link" onClick={() => void markRead(item)}>Mark read</button>}</article>) : <EmptyState icon={<Bell size={19} />} title="You're all caught up" text="New in-app updates will appear here." />}</section>
    <p className="messaging-limitation">Only in-app notifications are available in this milestone. Email, SMS, and web push require provider configuration and are not sent.</p>
  </>;
}

function emergencyCategoryLabel(category: EmergencyCategory) {
  return category.split("_").map((word) => word[0].toUpperCase() + word.slice(1)).join(" ");
}

function ProviderSearchPage({ pets, onSuccess, onError }: {
  pets: Pet[]; onSuccess: (message: string) => void; onError: (message: string) => void;
}) {
  const [kind, setKind] = useState<"veterinarian" | "groomer">("veterinarian");
  const [providers, setProviders] = useState<ProviderProfile[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<number | null>(null);
  const [slots, setSlots] = useState<ProviderAvailability[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [petId, setPetId] = useState<number>(pets[0]?.id ?? 0);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    setLoading(true);
    api.providers(kind).then((results) => {
      setProviders(results);
      setSelectedProvider((current) => results.some((provider) => provider.id === current) ? current : results[0]?.id ?? null);
    }).catch((reason: unknown) => {
      onError(reason instanceof Error ? reason.message : "Unable to find providers.");
    }).finally(() => setLoading(false));
  }, [kind, onError, refresh]);

  useEffect(() => {
    if (!selectedProvider) {
      setSlots([]);
      return;
    }
    api.providerAvailability(selectedProvider).then(setSlots).catch((reason: unknown) => {
      onError(reason instanceof Error ? reason.message : "Unable to load provider availability.");
    });
  }, [selectedProvider, onError, refresh]);

  useEffect(() => {
    api.appointments().then(setAppointments).catch((reason: unknown) => {
      onError(reason instanceof Error ? reason.message : "Unable to load your appointments.");
    });
  }, [onError, refresh]);

  async function book(slot: ProviderAvailability) {
    if (!petId) {
      onError("Add a pet profile before booking an appointment.");
      return;
    }
    try {
      await api.bookAppointment({ pet_id: petId, availability_id: slot.id });
      setRefresh((value) => value + 1);
      onSuccess("Booking request sent. It will remain pending until the provider responds.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to book this time.");
    }
  }

  async function cancel(appointment: Appointment) {
    if (!window.confirm("Cancel this appointment request?")) return;
    try {
      await api.updateAppointmentStatus(appointment.id, "cancelled");
      setRefresh((value) => value + 1);
      onSuccess("Appointment cancelled.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to cancel this appointment.");
    }
  }

  return <>
    <PageHeading kicker="CARE FROM VERIFIED PROVIDERS" title="Find a care provider" subtitle="Provider profiles are shown only for approved veterinarian and groomer accounts." />
    <section className="provider-filter-bar"><div className="provider-kind-switch"><button className={kind === "veterinarian" ? "selected" : ""} onClick={() => setKind("veterinarian")}><Stethoscope size={15} /> Veterinarians</button><button className={kind === "groomer" ? "selected" : ""} onClick={() => setKind("groomer")}><Sparkles size={15} /> Groomers</button></div><label>For your pet<select value={petId} onChange={(event) => setPetId(Number(event.target.value))}>{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select></label></section>
    <div className="provider-search-layout"><section className="provider-list">{loading ? <div className="content-card"><p className="detail-copy">Finding verified providers…</p></div> : providers.length ? providers.map((provider) => <button className={`provider-card ${selectedProvider === provider.id ? "provider-selected" : ""}`} key={provider.id} onClick={() => setSelectedProvider(provider.id)}><span className="provider-avatar">{provider.kind === "groomer" ? "✂" : <Stethoscope size={20} />}</span><span className="provider-card-copy"><strong>{provider.display_name}</strong><small><BadgeCheck size={13} /> Verified {provider.kind === "groomer" ? "groomer" : "veterinarian"}</small><span>{provider.service_area || "Service area not listed"} · {provider.service_fee ? `${provider.service_fee.toFixed(2)} consultation fee` : "Fee not listed"}</span></span><span className="select-chevron">→</span></button>) : <div className="content-card"><EmptyState icon={<Stethoscope size={20} />} title="No provider profiles yet" text="Only verified professionals with a published profile appear here." /></div>}</section>
      <section className="content-card slot-panel"><div className="section-title-row"><div><span className="section-kicker">AVAILABLE TIMES</span><h2>{providers.find((provider) => provider.id === selectedProvider)?.display_name ?? "Choose a provider"}</h2></div></div>{slots.length ? <div className="provider-slot-list">{slots.map((slot) => <article className="provider-slot" key={slot.id}><span><strong>{new Date(slot.starts_at).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</strong><small>{new Date(slot.starts_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })} – {new Date(slot.ends_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</small></span><button className="button button-soft" disabled={!pets.length} onClick={() => void book(slot)}>Request</button></article>)}</div> : <p className="detail-copy">{selectedProvider ? "No upcoming availability is published yet." : "Select a provider to view published availability."}</p>}</section>
    </div>
    <section className="content-card admin-section"><div className="section-title-row"><div><span className="section-kicker">YOUR CARE HISTORY</span><h2>Appointments</h2></div></div>{appointments.length ? <div className="provider-slot-list">{appointments.map((appointment) => <article className="provider-slot appointment-history-row" key={appointment.id}><span><strong>{roleLabel(appointment.service_kind)} · {petByIdName(pets, appointment.pet_id)}</strong><small>{new Date(appointment.starts_at).toLocaleString()}</small></span><span className={`application-status status-${appointment.status === "confirmed" || appointment.status === "completed" ? "approved" : appointment.status === "rejected" || appointment.status === "cancelled" ? "rejected" : "pending"}`}>{appointment.status}</span>{["pending", "confirmed"].includes(appointment.status) && <button className="quiet-button" onClick={() => void cancel(appointment)}>Cancel</button>}</article>)}</div> : <p className="detail-copy">Your appointment requests and history will appear here.</p>}</section>
  </>;
}

function ProviderWorkspace({ role, onSuccess, onError }: {
  role: "veterinarian" | "groomer"; onSuccess: (message: string) => void; onError: (message: string) => void;
}) {
  const [profile, setProfile] = useState<ProviderProfile | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.myProviderProfile().catch((reason: unknown) => {
        if (reason instanceof Error && reason.message.includes("Create your provider profile")) return null;
        throw reason;
      }),
      api.appointments(),
    ]).then(([savedProfile, bookings]) => {
      setProfile(savedProfile);
      setAppointments(bookings);
    }).catch((reason: unknown) => {
      onError(reason instanceof Error ? reason.message : "Unable to load your provider workspace.");
    }).finally(() => setLoading(false));
  }, [onError, refresh]);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const saved = await api.saveProviderProfile({
        display_name: String(form.get("display_name")),
        bio: String(form.get("bio")),
        service_area: String(form.get("service_area")) || null,
        service_fee: Number(form.get("service_fee") || 0),
      });
      setProfile(saved);
      onSuccess("Your verified provider profile is saved.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to save your provider profile.");
    }
  }

  async function addSlot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await api.addAvailability({
        starts_at: new Date(String(form.get("starts_at"))).toISOString(),
        ends_at: new Date(String(form.get("ends_at"))).toISOString(),
      });
      formElement.reset();
      onSuccess("Availability published.");
      setRefresh((value) => value + 1);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to publish this availability.");
    }
  }

  async function updateStatus(appointment: Appointment, status: "confirmed" | "rejected" | "completed") {
    try {
      await api.updateAppointmentStatus(appointment.id, status);
      setRefresh((value) => value + 1);
      onSuccess(`Appointment ${status}.`);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to update this appointment.");
    }
  }

  if (loading) return <PageHeading kicker={`${roleLabel(role).toUpperCase()} WORKSPACE`} title="Your care practice" subtitle="Loading your verified provider tools…" />;
  return <>
    <PageHeading kicker={`${roleLabel(role).toUpperCase()} WORKSPACE`} title="Your care practice" subtitle="Manage your public profile, publish open times, and respond to appointment requests." />
    <section className="provider-workspace-grid"><div className="content-card"><div className="section-title-row"><div><span className="section-kicker">PUBLIC PROFILE</span><h2>{profile ? "Your listing" : "Create your listing"}</h2></div><span className="application-status status-approved"><BadgeCheck size={12} /> Verified</span></div><form className="modal-form provider-profile-form" onSubmit={saveProfile}><label>Display name<input name="display_name" required minLength={2} maxLength={160} defaultValue={profile?.display_name ?? ""} placeholder="Clinic or business name" /></label><label>About your services<textarea name="bio" required minLength={10} maxLength={3000} rows={4} defaultValue={profile?.bio ?? ""} placeholder="Describe your professional services." /></label><div className="form-grid"><label>Service area<input name="service_area" maxLength={160} defaultValue={profile?.service_area ?? ""} placeholder="City or neighborhood" /></label><label>Fee <span className="optional">optional</span><input name="service_fee" type="number" min="0" step="0.01" defaultValue={profile?.service_fee ?? 0} /></label></div><button className="button button-primary" type="submit">Save profile</button></form></div>
      <div className="content-card"><div className="section-title-row"><div><span className="section-kicker">OPEN TIMES</span><h2>Publish availability</h2></div></div>{profile ? <form className="modal-form provider-profile-form" onSubmit={addSlot}><label>Starts<input type="datetime-local" name="starts_at" required /></label><label>Ends<input type="datetime-local" name="ends_at" required /></label><button className="button button-soft" type="submit"><Plus size={15} /> Add time slot</button><p className="detail-copy">Times must be in the future and may not overlap your existing slots.</p></form> : <p className="detail-copy">Save your provider profile first to publish availability.</p>}</div></section>
    <section className="content-card admin-section"><div className="section-title-row"><div><span className="section-kicker">BOOKING REQUESTS</span><h2>Appointments <span className="count-pill">{appointments.filter((item) => item.status === "pending").length}</span></h2></div></div>{appointments.length ? <div className="provider-slot-list">{appointments.map((appointment) => <article className="provider-slot appointment-history-row" key={appointment.id}><span><strong>{roleLabel(appointment.service_kind)} · Pet #{appointment.pet_id}</strong><small>{new Date(appointment.starts_at).toLocaleString()} · account #{appointment.owner_id}</small></span><span className={`application-status status-${appointment.status === "confirmed" || appointment.status === "completed" ? "approved" : appointment.status === "rejected" || appointment.status === "cancelled" ? "rejected" : "pending"}`}>{appointment.status}</span>{appointment.status === "pending" && <><button className="quiet-button" onClick={() => void updateStatus(appointment, "confirmed")}>Confirm</button><button className="quiet-button" onClick={() => void updateStatus(appointment, "rejected")}>Decline</button></>}{appointment.status === "confirmed" && <button className="quiet-button" onClick={() => void updateStatus(appointment, "completed")}>Complete</button>}</article>)}</div> : <p className="detail-copy">No appointment requests yet.</p>}</section>
  </>;
}

function petByIdName(pets: Pet[], id: number) {
  return pets.find((pet) => pet.id === id)?.name ?? `Pet #${id}`;
}

function VerificationPage({ role, onSuccess, onError }: {
  role: string; onSuccess: (message: string) => void; onError: (message: string) => void;
}) {
  const [applications, setApplications] = useState<ProfessionalApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    api.myProfessionalApplications().then(setApplications).catch((reason: unknown) => {
      onError(reason instanceof Error ? reason.message : "Unable to load your verification requests.");
    }).finally(() => setLoading(false));
  }, [onError, refresh]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setSubmitting(true);
    try {
      await api.submitProfessionalApplication({
        requested_role: String(form.get("role")) as ProfessionalRole,
        organization_name: String(form.get("organization_name")),
        credential_summary: String(form.get("credential_summary")),
      });
      formElement.reset();
      setRefresh((value) => value + 1);
      onSuccess("Your verification request was submitted for administrator review.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to submit your request.");
    } finally {
      setSubmitting(false);
    }
  }

  return <>
    <PageHeading kicker="PROFESSIONAL ACCESS" title="Join the care community" subtitle="Professional access is granted only after an administrator reviews your application." />
    {role !== "owner" ? <section className="content-card verification-current"><span className="verified-mark"><BadgeCheck size={21} /></span><div><span className="section-kicker">CURRENT ACCOUNT ROLE</span><h2>{roleLabel(role)}</h2><p>Your professional role was assigned after review. The application process does not upload or verify documents automatically.</p></div></section> : <section className="verification-layout">
      <div className="content-card verification-form-card"><div className="section-title-row"><div><span className="section-kicker">REQUEST A ROLE</span><h2>Tell us about your work</h2></div></div>
        <p className="detail-copy">Submitting a request does not change your account permissions. Do not include sensitive identity numbers or private client information here.</p>
        <form className="modal-form verification-form" onSubmit={submit}>
          <label>Professional role<select name="role" required defaultValue="veterinarian"><option value="veterinarian">Veterinarian</option><option value="groomer">Grooming professional</option><option value="shelter">Shelter / adoption organization</option><option value="volunteer">Emergency volunteer</option></select></label>
          <label>Clinic, organization, or service name<input name="organization_name" required minLength={2} maxLength={160} placeholder="Organization name" /></label>
          <label>Credential summary<textarea name="credential_summary" required minLength={20} maxLength={4000} rows={5} placeholder="Describe relevant qualifications and how they can be independently checked." /></label>
          <p className="form-disclaimer">Credential document upload and external license checks are not available yet. An administrator must assess the information before granting professional access.</p>
          <button className="button button-primary button-full" type="submit" disabled={submitting}>{submitting ? "Sending request…" : "Submit for review"} <ArrowRightIcon /></button>
        </form>
      </div>
      <div className="content-card application-history"><span className="section-kicker">YOUR REQUESTS</span><h2>Review history</h2>{loading ? <p className="detail-copy">Loading your requests…</p> : applications.length ? applications.map((application) => <article className="application-history-row" key={application.id}><div><strong>{roleLabel(application.requested_role)}</strong><small>{application.organization_name} · {formatDate(application.created_at)}</small>{application.review_notes && <p>{application.review_notes}</p>}</div><ApplicationStatus status={application.status} /></article>) : <p className="detail-copy">No requests yet. Your current account stays an owner account until a request is approved.</p>}</div>
    </section>}
  </>;
}

function AdministrationPage({ onSuccess, onError }: {
  onSuccess: (message: string) => void; onError: (message: string) => void;
}) {
  const [applications, setApplications] = useState<ProfessionalApplication[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    Promise.all([api.professionalApplications(), api.adminUsers()]).then(([pending, accounts]) => {
      setApplications(pending);
      setUsers(accounts);
    }).catch((reason: unknown) => {
      onError(reason instanceof Error ? reason.message : "Unable to load administrator data.");
    }).finally(() => setLoading(false));
  }, [onError, refresh]);

  async function review(application: ProfessionalApplication, decision: "approved" | "rejected") {
    const message = decision === "approved"
      ? `Approve ${roleLabel(application.requested_role)} access for ${application.organization_name}?`
      : `Reject the verification request from ${application.organization_name}?`;
    if (!window.confirm(message)) return;
    try {
      await api.reviewProfessionalApplication(application.id, decision);
      setRefresh((value) => value + 1);
      onSuccess(decision === "approved" ? "Professional access approved and recorded." : "Verification request rejected and recorded.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to review this request.");
    }
  }

  async function toggleSuspension(account: AdminUser) {
    const suspended = !account.is_suspended;
    if (!window.confirm(`${suspended ? "Suspend" : "Reinstate"} ${account.full_name}'s account?`)) return;
    try {
      await api.setUserSuspension(account.id, suspended);
      setRefresh((value) => value + 1);
      onSuccess(suspended ? "Account suspended; active API access is revoked." : "Account reinstated.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to update this account.");
    }
  }

  return <>
    <PageHeading kicker="ADMINISTRATOR TOOLS" title="Review & account access" subtitle="Verification decisions and suspensions are recorded in the audit log." />
    {loading ? <section className="content-card"><p className="detail-copy">Loading administrator data…</p></section> : <>
      <section className="content-card admin-section"><div className="section-title-row"><div><span className="section-kicker">PROFESSIONAL VERIFICATION</span><h2>Pending requests <span className="count-pill">{applications.length}</span></h2></div></div>
        {applications.length ? <div className="admin-application-list">{applications.map((application) => <article className="admin-application" key={application.id}><div className="admin-application-header"><div><span className="section-kicker">{roleLabel(application.requested_role)}</span><h3>{application.organization_name}</h3><small>Account #{application.user_id} · submitted {formatDate(application.created_at)}</small></div><ApplicationStatus status={application.status} /></div><p>{application.credential_summary}</p><div className="admin-actions"><button className="button button-soft" onClick={() => void review(application, "approved")}><Check size={15} /> Approve</button><button className="quiet-button" onClick={() => void review(application, "rejected")}>Reject</button></div></article>)}</div> : <EmptyState icon={<BadgeCheck size={19} />} title="No requests waiting" text="New professional applications will appear here for review." />}</section>
      <section className="content-card admin-section"><div className="section-title-row"><div><span className="section-kicker">ACCOUNT ACCESS</span><h2>Accounts <span className="count-pill">{users.length}</span></h2></div></div>
        <div className="admin-user-list">{users.map((account) => <article className="admin-user-row" key={account.id}><span className="profile-avatar">{initials(account.full_name)}</span><span className="admin-user-info"><strong>{account.full_name}</strong><small>{account.email} · {roleLabel(account.role)}</small></span><span className={`account-state ${account.is_suspended ? "suspended" : ""}`}>{account.is_suspended ? "Suspended" : "Active"}</span>{account.role !== "admin" && <button className="quiet-button" onClick={() => void toggleSuspension(account)}>{account.is_suspended ? "Reinstate" : "Suspend"}</button>}</article>)}</div>
      </section>
    </>}
  </>;
}

function roleLabel(role: string) {
  const labels: Record<string, string> = {
    owner: "Pet owner",
    veterinarian: "Veterinarian",
    groomer: "Grooming professional",
    shelter: "Shelter organization",
    volunteer: "Emergency volunteer",
    admin: "Administrator",
  };
  return labels[role] ?? role;
}

function ApplicationStatus({ status }: { status: string }) {
  return <span className={`application-status status-${status}`}>{status}</span>;
}

function PageHeading({ kicker, title, subtitle, action }: { kicker: string; title: string; subtitle: string; action?: ReactNode }) {
  return <section className="welcome-row page-heading"><div><span className="page-kicker">{kicker}</span><h1>{title}</h1><p>{subtitle}</p></div>{action}</section>;
}

function EmptyState({ icon, title, text, action, onClick }: { icon: ReactNode; title: string; text: string; action?: string; onClick?: () => void }) {
  return <div className="empty-state"><span className="empty-icon">{icon}</span><strong>{title}</strong><p>{text}</p>{action && onClick && <button className="text-link" onClick={onClick}>{action} <span>→</span></button>}</div>;
}

function CommunityPage({ role, userId, pets, onSuccess, onError }: {
  role: string; userId: number; pets: Pet[]; onSuccess: (message: string) => void; onError: (message: string) => void;
}) {
  const [listings, setListings] = useState<AdoptionListing[]>([]);
  const [reports, setReports] = useState<MissingPetReport[]>([]);
  const [sightings, setSightings] = useState<Record<number, PetSighting[]>>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [adoptionData, missingData] = await Promise.all([api.adoptionListings(), api.missingPetReports()]);
      setListings(adoptionData);
      setReports(missingData);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to load community listings.");
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function submitMissing(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const petId = String(data.get("pet_id") ?? "");
    const selectedPet = pets.find((pet) => pet.id === Number(petId));
    try {
      await api.createMissingPetReport({
        pet_id: petId ? Number(petId) : null,
        pet_name: selectedPet?.name ?? String(data.get("pet_name")),
        species: selectedPet?.species ?? String(data.get("species")),
        description: String(data.get("description")),
        service_area: String(data.get("service_area")),
        contact_instructions: String(data.get("contact_instructions")),
      });
      event.currentTarget.reset();
      await refresh();
      onSuccess("Missing-pet report published.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to publish this report.");
    }
  }

  async function submitAdoption(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await api.createAdoptionListing({
        pet_name: String(data.get("pet_name")),
        species: String(data.get("species")),
        breed: String(data.get("breed")) || null,
        description: String(data.get("description")),
        service_area: String(data.get("service_area")),
      });
      event.currentTarget.reset();
      await refresh();
      onSuccess("Adoption listing published.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to publish the listing.");
    }
  }

  async function submitSighting(report: MissingPetReport, event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await api.createPetSighting(report.id, {
        description: String(data.get("description")),
        service_area: String(data.get("service_area")),
      });
      setSightings((current) => ({
        ...current,
        [report.id]: [...(current[report.id] ?? []), {
          id: Date.now(), report_id: report.id, description: String(data.get("description")),
          service_area: String(data.get("service_area")), created_at: new Date().toISOString(),
        }],
      }));
      event.currentTarget.reset();
      onSuccess("Sighting shared with the pet's owner.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to submit this sighting.");
    }
  }

  async function markFound(report: MissingPetReport) {
    try {
      await api.updateMissingPetStatus(report.id, "found");
      await refresh();
      onSuccess(`${report.pet_name}'s report was marked found.`);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to update this report.");
    }
  }

  async function setListingStatus(listing: AdoptionListing, status: AdoptionListing["status"]) {
    try {
      await api.updateAdoptionStatus(listing.id, status);
      await refresh();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to update this listing.");
    }
  }

  async function loadSightings(report: MissingPetReport) {
    try {
      const reportSightings = await api.petSightings(report.id);
      setSightings((current) => ({ ...current, [report.id]: reportSightings }));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Unable to load sightings.");
    }
  }

  return <>
    <PageHeading kicker="COMMUNITY CARE" title="Adoption & lost pets" subtitle="Share shelter adoption listings, report a missing pet, or help with a sighting." />
    {role === "shelter" && <section className="content-card community-form-card">
      <div className="section-title-row"><div><span className="section-kicker">SHELTER WORKSPACE</span><h2>Share an adoption listing</h2></div></div>
      <form className="modal-form community-form" onSubmit={submitAdoption}>
        <div className="form-grid"><label>Pet name<input name="pet_name" required maxLength={80} /></label><label>Species<input name="species" required maxLength={40} /></label></div>
        <div className="form-grid"><label>Breed <span className="optional">optional</span><input name="breed" maxLength={80} /></label><label>Area<input name="service_area" required maxLength={160} /></label></div>
        <label>Details<textarea name="description" required minLength={10} maxLength={3000} rows={3} placeholder="Temperament, needs, and adoption details" /></label>
        <button className="button button-primary" type="submit">Publish listing <ArrowRight size={16} /></button>
      </form>
    </section>}
    {(role === "owner" || role === "admin") && <section className="content-card community-form-card">
      <div className="section-title-row"><div><span className="section-kicker">LOST PET SUPPORT</span><h2>Report a missing pet</h2></div></div>
      <p className="community-privacy-note">Reports and contact instructions are visible to signed-in PetVerse users. Share a general area only; do not post a home address.</p>
      <form className="modal-form community-form" onSubmit={submitMissing}>
        {pets.length > 0 && <label>Pet profile <span className="optional">optional</span><select name="pet_id" defaultValue=""><option value="">Enter details manually</option>{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select></label>}
        <div className="form-grid"><label>Pet name<input name="pet_name" required maxLength={80} /></label><label>Species<input name="species" required maxLength={40} /></label></div>
        <div className="form-grid"><label>Last seen area<input name="service_area" required maxLength={160} placeholder="Neighborhood or nearby landmark" /></label><label>Contact instructions<input name="contact_instructions" required maxLength={240} placeholder="How should finders contact you?" /></label></div>
        <label>Description<textarea name="description" required minLength={10} maxLength={3000} rows={3} placeholder="Appearance, collar, and useful identifying details" /></label>
        <button className="button button-primary" type="submit">Publish missing-pet report <ArrowRight size={16} /></button>
      </form>
    </section>}
    {loading ? <section className="content-card"><p className="detail-copy">Loading community listings…</p></section> : <>
      <section className="community-grid">
        <div className="content-card community-list-card">
          <div className="section-title-row"><div><span className="section-kicker">SHELTER PARTNERS</span><h2>Pets looking for homes</h2></div></div>
          {listings.length ? listings.map((listing) => <article className="community-item" key={listing.id}>
            <span className="community-icon"><Home size={18} /></span><div className="community-copy"><strong>{listing.pet_name} · {listing.species}</strong><small>{listing.breed || "Breed not listed"} · {listing.service_area}</small><p>{listing.description}</p></div>
            {role === "shelter" && <select aria-label={`Update ${listing.pet_name} adoption status`} value={listing.status} onChange={(event) => void setListingStatus(listing, event.target.value as AdoptionListing["status"])}><option value="available">Available</option><option value="pending">Pending</option><option value="adopted">Adopted</option><option value="withdrawn">Withdrawn</option></select>}
          </article>) : <p className="detail-copy">No adoption listings available right now.</p>}
        </div>
        <div className="content-card community-list-card">
          <div className="section-title-row"><div><span className="section-kicker">NEIGHBORHOOD WATCH</span><h2>Missing pets</h2></div></div>
          {reports.length ? reports.map((report) => <article className="community-item missing-item" key={report.id}>
            <span className="community-icon missing"><PawPrint size={18} /></span><div className="community-copy"><strong>{report.pet_name} · {report.species}</strong><small>Last seen near {report.service_area} · {formatDate(report.created_at)}</small><p>{report.description}</p><small>Contact: {report.contact_instructions}</small>
              <button className="text-link community-sightings-toggle" onClick={() => void loadSightings(report)}>Show sightings</button>
              {sightings[report.id]?.map((sighting) => <p className="sighting-note" key={sighting.id}><strong>{sighting.service_area}:</strong> {sighting.description}</p>)}
              {role !== "admin" && <form className="sighting-form" onSubmit={(event) => void submitSighting(report, event)}><input name="service_area" required maxLength={160} aria-label="Sighting area" placeholder="Area where you saw the pet" /><input name="description" required minLength={5} maxLength={1000} aria-label="Sighting details" placeholder="When and what you saw" /><button className="quiet-button" type="submit">Share sighting</button></form>}
              {(role === "admin" || (role === "owner" && report.owner_id === userId)) && <button className="quiet-button" onClick={() => void markFound(report)}>Mark found</button>}
            </div>
          </article>) : <p className="detail-copy">No active missing-pet reports.</p>}
        </div>
      </section>
    </>}
  </>;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-header"><div><span className="section-kicker">A LITTLE MORE LOVE</span><h2 id="modal-title">{title}</h2></div><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={19} /></button></div>{children}</section></div>;
}
