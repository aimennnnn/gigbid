"use client";
import { useRouter } from "next/navigation";
import { ProfileForm } from "@/components/ProfileForm";
import { saveSession, session } from "@/lib/client";

export default function Onboarding() {
  const router = useRouter();
  return (
    <div className="card">
      <h1>Set up GigBid</h1>
      <p className="muted">Two minutes. You can change all of this later in Settings.</p>
      <ProfileForm
        submitLabel="Save and open my inbox"
        onSaved={() => {
          const s = session();
          if (s) saveSession({ ...s, onboarded: true });
          router.replace("/inbox");
        }}
      />
    </div>
  );
}
