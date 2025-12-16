import { useRef, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Play } from "lucide-react";
import { introVideoConfig, VideoConfig } from "@/config/platformResources";

interface IntroVideoPlayerProps {
  config: VideoConfig;
}

function DirectVideoPlayer({ config }: IntroVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleLoadedMetadata = () => {
      video.currentTime = config.startTime;
      video.playbackRate = config.playbackRate;
      setIsLoaded(true);
    };

    const handleTimeUpdate = () => {
      if (video.currentTime >= config.endTime) {
        video.currentTime = config.startTime;
      }
    };

    const handleError = () => {
      setError(true);
    };

    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("error", handleError);

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("error", handleError);
    };
  }, [config.startTime, config.endTime, config.playbackRate]);

  if (error) {
    return <VideoPlaceholder message="Video failed to load" />;
  }

  return (
    <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-background-surface">
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-background-surface">
          <div className="animate-pulse flex flex-col items-center gap-3">
            <Play className="w-12 h-12 text-gray-500" />
            <span className="text-gray-500 text-sm">Loading video...</span>
          </div>
        </div>
      )}
      <video
        ref={videoRef}
        className="w-full h-full object-cover"
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
      >
        <source src={config.src} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
    </div>
  );
}

function GoogleDrivePlayer({ config }: IntroVideoPlayerProps) {
  const embedUrl = config.src.includes("/file/d/")
    ? config.src.replace("/view", "/preview")
    : `https://drive.google.com/file/d/${config.src}/preview`;

  return (
    <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-background-surface">
      <iframe
        src={embedUrl}
        className="w-full h-full"
        allow="autoplay; encrypted-media"
        allowFullScreen
        title="UnifAI Introduction Video"
        frameBorder="0"
      />
    </div>
  );
}

function VideoPlaceholder({ message }: { message: string }) {
  return (
    <div className="w-full aspect-video rounded-xl bg-background-surface border border-gray-800 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-gray-500">
        <Play className="w-16 h-16" />
        <span className="text-sm">{message}</span>
        <span className="text-xs text-gray-600">
          Add a video URL in platformResources.ts
        </span>
      </div>
    </div>
  );
}

export default function IntroVideoSection() {
  const config = introVideoConfig;

  if (!config.enabled || !config.src) {
    return null;
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="mb-10"
    >
      {/* <div className="mb-4">
        <h2 className="text-xl font-semibold text-white mb-2">
          {config.title || "See UnifAI in Action"}
        </h2>
        {config.description && (
          <p className="text-gray-400 text-sm">
            {config.description}
          </p>
        )}
      </div> */}
      <Card className="bg-background-card border-gray-800 p-2 overflow-hidden">
        {config.type === "direct" ? (
          <DirectVideoPlayer config={config} />
        ) : (
          <GoogleDrivePlayer config={config} />
        )}
      </Card>
    </motion.section>
  );
}