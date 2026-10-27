import type {
  AdoptionListing, AdminUser, AppNotification, Appointment, CareAssistantReply, CareTask, DashboardData, EmergencyCategory,
  ChatMessage, Conversation, EmergencyRequest, MedicalRecord, Pet, ProfessionalApplication, ProfessionalRole,
  MissingPetReport, PetSighting, ProviderAvailability, ProviderProfile, User, VolunteerProfile,
} from "../types";

const baseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "petverse_access_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function saveToken(token: string | null): void {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${baseUrl}/api/v1${path}`, { ...init, headers });
  if (!response.ok) {
    const result = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(result?.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

interface AuthResponse {
  access_token: string;
  user: User;
}

interface AuthMessageResponse {
  message: string;
}

export const api = {
  googleAuthConfig: () => request<{ client_id: string | null }>("/auth/google/config"),
  googleLogin: (credential: string) =>
    request<AuthResponse>("/auth/google", { method: "POST", body: JSON.stringify({ credential }) }),
  register: (data: { full_name: string; email: string; password: string }) =>
    request<AuthMessageResponse>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  verifyEmail: (token: string) =>
    request<AuthMessageResponse>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),
  resendVerification: (email: string) =>
    request<AuthMessageResponse>("/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) }),
  requestPasswordReset: (email: string) =>
    request<AuthMessageResponse>("/auth/password-reset/request", { method: "POST", body: JSON.stringify({ email }) }),
  confirmPasswordReset: (token: string, password: string) =>
    request<AuthMessageResponse>("/auth/password-reset/confirm", {
      method: "POST", body: JSON.stringify({ token, password }),
    }),
  me: () => request<User>("/auth/me"),
  dashboard: () => request<DashboardData>("/dashboard"),
  pets: () => request<Pet[]>("/pets"),
  createPet: (data: Partial<Pet>) =>
    request<Pet>("/pets", { method: "POST", body: JSON.stringify(data) }),
  updatePet: (id: number, data: Partial<Pet>) =>
    request<Pet>(`/pets/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  archivePet: (id: number) => request<void>(`/pets/${id}`, { method: "DELETE" }),
  tasks: () => request<CareTask[]>("/care-tasks"),
  createTask: (data: Pick<
    CareTask,
    "pet_id" | "title" | "category" | "instructions" | "due_at" |
    "repeat_interval_minutes" | "reminder_days_before"
  >) =>
    request<CareTask>("/care-tasks", { method: "POST", body: JSON.stringify(data) }),
  completeTask: (id: number) => request<CareTask>(`/care-tasks/${id}/complete`, { method: "PATCH" }),
  askCareAssistant: (question: string, pet_species?: string) =>
    request<CareAssistantReply>("/care-assistant", {
      method: "POST", body: JSON.stringify({ question, pet_species }),
    }),
  adoptionListings: () => request<AdoptionListing[]>("/adoptions"),
  createAdoptionListing: (data: Omit<AdoptionListing, "id" | "shelter_user_id" | "status" | "created_at">) =>
    request<AdoptionListing>("/adoptions", { method: "POST", body: JSON.stringify(data) }),
  updateAdoptionStatus: (id: number, status: AdoptionListing["status"]) =>
    request<AdoptionListing>(`/adoptions/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  missingPetReports: () => request<MissingPetReport[]>("/missing-pets"),
  createMissingPetReport: (data: {
    pet_id?: number | null; pet_name: string; species: string; description: string;
    service_area: string; contact_instructions: string;
  }) => request<MissingPetReport>("/missing-pets", { method: "POST", body: JSON.stringify(data) }),
  updateMissingPetStatus: (id: number, status: MissingPetReport["status"]) =>
    request<MissingPetReport>(`/missing-pets/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  createPetSighting: (id: number, data: { description: string; service_area: string }) =>
    request<PetSighting>(`/missing-pets/${id}/sightings`, { method: "POST", body: JSON.stringify(data) }),
  petSightings: (id: number) => request<PetSighting[]>(`/missing-pets/${id}/sightings`),
  records: (petId: number) => request<MedicalRecord[]>(`/pets/${petId}/records`),
  createRecord: (petId: number, data: Pick<MedicalRecord, "record_type" | "title" | "details">) =>
    request<MedicalRecord>(`/pets/${petId}/records`, { method: "POST", body: JSON.stringify(data) }),
  myProfessionalApplications: () => request<ProfessionalApplication[]>("/professional-applications/me"),
  submitProfessionalApplication: (data: {
    requested_role: ProfessionalRole;
    organization_name: string;
    credential_summary: string;
  }) => request<ProfessionalApplication>("/professional-applications", { method: "POST", body: JSON.stringify(data) }),
  professionalApplications: () => request<ProfessionalApplication[]>("/admin/professional-applications"),
  reviewProfessionalApplication: (id: number, decision: "approved" | "rejected", review_notes?: string) =>
    request<ProfessionalApplication>(`/admin/professional-applications/${id}/review`, {
      method: "POST", body: JSON.stringify({ decision, review_notes }),
    }),
  adminUsers: () => request<AdminUser[]>("/admin/users"),
  setUserSuspension: (id: number, suspended: boolean) =>
    request<AdminUser>(`/admin/users/${id}/suspension?suspended=${suspended}`, { method: "PATCH" }),
  providers: (kind?: "veterinarian" | "groomer") =>
    request<ProviderProfile[]>(`/providers${kind ? `?kind=${kind}` : ""}`),
  providerAvailability: (id: number) => request<ProviderAvailability[]>(`/providers/${id}/availability`),
  myProviderProfile: () => request<ProviderProfile>("/providers/me/profile"),
  saveProviderProfile: (data: Omit<ProviderProfile, "id" | "user_id" | "kind">) =>
    request<ProviderProfile>("/providers/me/profile", { method: "PUT", body: JSON.stringify(data) }),
  addAvailability: (data: Pick<ProviderAvailability, "starts_at" | "ends_at">) =>
    request<ProviderAvailability>("/providers/me/availability", { method: "POST", body: JSON.stringify(data) }),
  appointments: () => request<Appointment[]>("/appointments"),
  bookAppointment: (data: { pet_id: number; availability_id: number; owner_note?: string }) =>
    request<Appointment>("/appointments", { method: "POST", body: JSON.stringify(data) }),
  updateAppointmentStatus: (id: number, status: "confirmed" | "rejected" | "completed" | "cancelled") =>
    request<Appointment>(`/appointments/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  emergencyRequests: () => request<EmergencyRequest[]>("/emergencies/mine"),
  availableEmergencies: () => request<EmergencyRequest[]>("/emergencies/available"),
  createEmergency: (data: {
    category: EmergencyCategory;
    severity: "critical" | "urgent";
    description: string;
    pet_id?: number | null;
    location?: string | null;
  }) => request<EmergencyRequest>("/emergencies", { method: "POST", body: JSON.stringify(data) }),
  acceptEmergency: (id: number) => request<EmergencyRequest>(`/emergencies/${id}/accept`, { method: "POST" }),
  declineEmergency: (id: number) => request<void>(`/emergencies/${id}/decline`, { method: "POST" }),
  updateEmergencyStatus: (
    id: number,
    status: "responding" | "in_progress" | "completed" | "cancelled" | "escalated",
  ) => request<EmergencyRequest>(`/emergencies/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),
  volunteerProfile: () => request<VolunteerProfile>("/volunteers/me/profile"),
  updateVolunteerProfile: (data: { service_area?: string | null; is_available: boolean }) =>
    request<VolunteerProfile>("/volunteers/me/profile", { method: "PUT", body: JSON.stringify(data) }),
  notifications: () => request<AppNotification[]>("/notifications"),
  markNotificationRead: (id: number) =>
    request<AppNotification>(`/notifications/${id}/read`, { method: "PATCH" }),
  conversations: () => request<Conversation[]>("/conversations"),
  openConversation: (context_type: "appointment" | "emergency", context_id: number) =>
    request<Conversation>("/conversations", { method: "POST", body: JSON.stringify({ context_type, context_id }) }),
  messages: (conversationId: number) =>
    request<ChatMessage[]>(`/conversations/${conversationId}/messages`),
  sendMessage: (conversationId: number, body: string) =>
    request<ChatMessage>(`/conversations/${conversationId}/messages`, {
      method: "POST", body: JSON.stringify({ body }),
    }),
};
