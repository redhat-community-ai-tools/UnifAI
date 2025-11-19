import { motion } from "framer-motion";

export default function StatusBar() {
  const lastSyncTime = "10 minutes ago";
  const apiVersion = "v2.4.1";
  
  return (
    <footer className="h-8 bg-background-surface border-t border-gray-800 px-6 flex items-center justify-between text-xs text-gray-400">
      <div className="flex items-center space-x-4">
        <div className="flex items-center">
          <motion.div 
            className="w-2 h-2 rounded-full bg-success mr-2"
            animate={{ opacity: [1, 0.5, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span>System active</span>
        </div>
        <div>Last sync: {lastSyncTime}</div>
      </div>
      <div className="flex items-center space-x-4">
        <div>API {apiVersion}</div>
        <div>
          <a href="#" className="hover:text-white transition-colors">Docs</a>
        </div>
        <div>
          <a href="#" className="hover:text-white transition-colors">Support</a>
        </div>
      </div>
    </footer>
  );
}
