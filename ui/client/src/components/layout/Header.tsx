import React from "react";
import { useState } from "react";
import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { FaSearch, FaBell, FaInfoCircle, FaPlus, FaBars, FaMoon, FaSun, FaSignOutAlt, FaShare, FaCodeBranch } from "react-icons/fa";
import { FaShareNodes } from "react-icons/fa6";
import { motion } from "framer-motion";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import NotificationPanel from "@/components/shared/NotificationPanel";
import SharedPanel from "@/components/shared/SharedPanel";
import HelpPanel from "@/components/shared/HelpPanel";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from '@/contexts/AuthContext';
import { useNotifications } from '@/contexts/NotificationContext';
import { useShared } from '@/contexts/SharedContext';
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';

interface HeaderProps {
  title: string;
  onToggleSidebar: () => void;
}

export default function Header({ title, onToggleSidebar }: HeaderProps) {
  const [isNotificationPanelOpen, setIsNotificationPanelOpen] = useState(false);
  const [isHelpPanelOpen, setIsHelpPanelOpen] = useState(false);
  const { theme, toggleTheme, primaryHex, setPrimaryHex } = useTheme();
  const { user, logout } = useAuth();
  const { hasUnreadNotifications, pendingNotificationsCount } = useNotifications();
  const { isSharedPanelOpen, openSharedPanel, closeSharedPanel } = useShared();

  const colorOptions = [
    { hex: "#A60000", name: "Red" },
    { hex: "#147878", name: "Teal" },
    { hex: "#707070", name: "Gray" },
    { hex: "#8A2BE2", name: "Purple" },
  ];

  const getInitials = (name: string): string => {
    return name
      .split(' ')                         // Split by spaces
      .filter(Boolean)                    // Remove empty parts
      .map(part => part[0].toUpperCase()) // Take first letter of each part and capitalize
      .join('');                          // Join into a string
  }

  return (
    <header className="h-16 bg-background-surface border-b border-gray-800 flex items-center justify-between px-6 py-2">
      <div className="flex items-center">
        <button
          onClick={onToggleSidebar}
          className="mr-4 md:hidden text-gray-400 hover:text-gray-800 dark:hover:text-white"
        >
          <FaBars size={18} />
        </button>
        <motion.h1
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="font-heading font-bold text-xl text-white"
        >
          {title}
        </motion.h1>
      </div>
      <div className="flex items-center space-x-4">
        <SimpleTooltip content={<p>Search</p>}>
          <button className="p-2 rounded-full hover:bg-background-card text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors">
            <FaSearch />
          </button>
        </SimpleTooltip>

        {/* Color picker (dropdown) */}
        <div className="mr-2 w-19">
          <Select value={primaryHex} onValueChange={(value) => setPrimaryHex(value)}>
            <SelectTrigger>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: primaryHex }} />
              </div>
            </SelectTrigger>
            <SelectContent className="min-w-[var(--radix-select-trigger-width)] w-[var(--radix-select-trigger-width)]">
              {colorOptions.map(({ hex }) => (
                <SelectItem key={hex} value={hex}>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: hex }} />
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="relative">
          <SimpleTooltip content={<p>Shared System</p>}>
            <UmamiTrack event={UmamiEvents.SHARED_SYSTEM_BUTTON} includeUserData={false}>
              <button
                onClick={() => openSharedPanel('list')}
                className="p-2 rounded-full hover:bg-background-card text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors"
              >
                <FaShareNodes />
              </button>
            </UmamiTrack>
          </SimpleTooltip>
          
          {/* Shared Panel */}
          <SharedPanel 
            isOpen={isSharedPanelOpen}
            onClose={closeSharedPanel}
          />
        </div>

        <div className="relative">
          <SimpleTooltip content={<p>Notifications{hasUnreadNotifications ? ` (${pendingNotificationsCount})` : ''}</p>}>
              
            <UmamiTrack event={UmamiEvents.NOTIFICATIONS_BUTTON} includeUserData={false}>
              <button
                onClick={() => setIsNotificationPanelOpen(!isNotificationPanelOpen)}
                className="p-2 rounded-full hover:bg-background-card text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors relative"
              >
                <FaBell />
                {hasUnreadNotifications && (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500"
                  />
                )}
              </button>
            </UmamiTrack>
          </SimpleTooltip>
          
          {/* Notification Panel */}
          <NotificationPanel
            isOpen={isNotificationPanelOpen}
            onClose={() => setIsNotificationPanelOpen(false)}
          />
        </div>

        {/* Versions Button */}
        <div className="relative">
          <SimpleTooltip content={<p>Versions</p>}>
            <button
              onClick={() => setIsHelpPanelOpen(!isHelpPanelOpen)}
              className="p-2 rounded-full hover:bg-background-card text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors"
            >
              <FaCodeBranch />
            </button>
          </SimpleTooltip>
          <HelpPanel
            isOpen={isHelpPanelOpen}
            onClose={() => setIsHelpPanelOpen(false)}
          />
        </div>

        {/* Theme Switch */}
        <SimpleTooltip
          content={
            <p>
              {theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            </p>
          }
        >
          <button
            onClick={toggleTheme}
            className="p-2 rounded-full hover:bg-background-card text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors"
          >
            {theme === 'dark' ? <FaSun /> : <FaMoon />}
          </button>
        </SimpleTooltip>

        {/* User Profile */}
        <div className="px-4 py-3 border-l border-gray-800">
          <div className={`flex items-center space-x-3`}>
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: `linear-gradient(90deg, #6B7280, ${primaryHex})` }}
            >
              <span className="text-sm font-medium text-white">{getInitials(user?.name || '')}</span>
            </div>
            
            <motion.div
              initial={false}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
              className="flex-grow"
            >
              <h4 className="text-sm font-medium">{user?.name}</h4>
            </motion.div>
            
            <motion.div
              initial={false}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <SimpleTooltip content={<p>Sign out</p>}>
                <button className="mt-2 text-gray-400 hover:text-white">
                  <FaSignOutAlt />
                </button>
              </SimpleTooltip>
            </motion.div>
            
          </div>
        </div>
        
        {/* <Button size="sm" className="ml-2 bg-primary hover:bg-opacity-80">
          <FaPlus className="mr-2 h-3 w-3" />
          <span>New Pipeline</span>
        </Button> */}
      </div>
    </header>
  );
}
