export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  email_verified: boolean;
  is_suspended: boolean;
}

export type ProfessionalRole = "veterinarian" | "groomer" | "shelter" | "volunteer";

export interface ProfessionalApplication {
  id: number;
  user_id: number;
  requested_role: ProfessionalRole;
  organization_name: string;
  credential_summary: string;
  status: "pending" | "approved" | "rejected";
  review_notes: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface AdminUser extends User {
  created_at: string;
}

export interface ProviderProfile {
  id: number;
  user_id: number;
  kind: "veterinarian" | "groomer";
  display_name: string;
  bio: string;
  service_area: string | null;
  service_fee: number;
}

export interface ProviderAvailability {
  id: number;
  provider_id: number;
  starts_at: string;
  ends_at: string;
  is_available: boolean;
}

export interface Appointment {
  id: number;
  owner_id: number;
  pet_id: number;
  provider_id: number;
  availability_id: number;
  service_kind: string;
  status: "pending" | "confirmed" | "rejected" | "completed" | "cancelled";
  owner_note: string | null;
  created_at: string;
  starts_at: string;
  ends_at: string;
}

export type EmergencyCategory =
  | "breathing_difficulty"
  | "suspected_poisoning"
  | "serious_injury"
  | "severe_bleeding"
  | "seizure"
  | "heat_emergency"
  | "road_accident"
  | "missing_pet"
  | "injured_stray"
  | "other";

export interface EmergencyRequest {
  id: number;
  owner_id: number;
  pet_id: number | null;
  category: EmergencyCategory;
  severity: "critical" | "urgent";
  description: string;
  location: string | null;
  assigned_volunteer_id: number | null;
  status: "submitted" | "assigned" | "responding" | "in_progress" | "completed" | "cancelled" | "escalated";
  created_at: string;
  updated_at: string;
}

export interface VolunteerProfile {
  id: number;
  user_id: number;
  service_area: string | null;
  is_available: boolean;
}

export interface AppNotification {
  id: number;
  kind: string;
  message: string;
  emergency_request_id: number | null;
  is_read: boolean;
  created_at: string;
}

export interface Conversation {
  id: number;
  appointment_id: number | null;
  emergency_request_id: number | null;
  other_user_id: number;
  other_user_name: string;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender_id: number;
  sender_name: string;
  body: string;
  created_at: string;
  read_at: string | null;
}

export interface Pet {
  id: number;
  name: string;
  species: string;
  breed: string | null;
  birth_date: string | null;
  sex: string | null;
  weight_kg: number | null;
  allergies: string | null;
  notes: string | null;
  photo_url: string | null;
  archived: boolean;
}

export interface AdoptionListing {
  id: number;
  shelter_user_id: number;
  pet_name: string;
  species: string;
  breed: string | null;
  description: string;
  service_area: string;
  status: "available" | "pending" | "adopted" | "withdrawn";
  created_at: string;
}

export interface MissingPetReport {
  id: number;
  owner_id: number;
  pet_id: number | null;
  pet_name: string;
  species: string;
  description: string;
  service_area: string;
  contact_instructions: string;
  status: "missing" | "found" | "closed";
  created_at: string;
}

export interface PetSighting {
  id: number;
  report_id: number;
  description: string;
  service_area: string;
  created_at: string;
}

export interface CareAssistantReply {
  answer: string;
  urgent: boolean;
}

export interface CareTask {
  id: number;
  pet_id: number;
  title: string;
  category: string;
  instructions: string | null;
  due_at: string;
  repeat_interval_minutes: number | null;
  reminder_days_before: number;
  reminder_sent_at: string | null;
  completed: boolean;
}

export interface MedicalRecord {
  id: number;
  pet_id: number;
  record_type: string;
  title: string;
  details: string;
  recorded_at: string;
  professional_record: boolean;
}

export interface DashboardData {
  role: string;
  pet_count: number;
  due_tasks: number;
  completed_tasks: number;
  recent_records: number;
  upcoming_tasks: CareTask[];
  pending_appointments: number;
  active_appointments: number;
  active_emergencies: number;
  pending_applications: number;
  suspended_users: number;
}
