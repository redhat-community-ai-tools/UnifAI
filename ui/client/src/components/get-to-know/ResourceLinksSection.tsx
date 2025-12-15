import ResourceLinkCard from "./ResourceLinkCard";
import { platformResources } from "@/config/platformResources";

export default function ResourceLinksSection() {
  return (
    <section className="mb-10">
      <h2 className="text-xl font-semibold text-white mb-6">
        Quick Links & Resources
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {platformResources.map((resource, index) => (
          <ResourceLinkCard
            key={resource.id}
            icon={resource.icon}
            title={resource.title}
            description={resource.description}
            url={resource.url}
            index={index}
          />
        ))}
      </div>
    </section>
  );
}