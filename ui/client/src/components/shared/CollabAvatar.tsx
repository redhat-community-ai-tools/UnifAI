import React from "react";
import type { MemberDisplay } from "@/utils/memberDisplay";

export function CollabAvatar({ member, size = "sm" }: { member: MemberDisplay; size?: "xs" | "sm" }) {
  const sizeClasses = { xs: "w-5 h-5 text-[9px]", sm: "w-7 h-7 text-[10px]" };
  return (
    <div className={`${sizeClasses[size]} rounded-full bg-gradient-to-br ${member.color} flex items-center justify-center font-bold text-white flex-shrink-0`}>
      {member.initials}
    </div>
  );
}

export default CollabAvatar;
