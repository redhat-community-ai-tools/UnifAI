import React from "react";
import { Link, useLocation } from "wouter";
import { useProject } from "@/contexts/ProjectContext";
import { 
  FaTachometerAlt, FaCogs, FaFileAlt, 
  FaChartLine, FaUserShield, FaCog, FaSignOutAlt,
  FaRobot, FaFile, FaChevronLeft, FaChevronRight,
  FaInfoCircle, FaBook, FaComment
} from "react-icons/fa";
import { FaJira, FaSlack, FaBars } from "react-icons/fa";
import { motion } from "framer-motion";
import { useState } from "react";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { useAuth, User } from '@/contexts/AuthContext';

export default function Sidebar() {
  const [location] = useLocation();
  const { currentProject } = useProject();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Save collapse state when it changes
  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed);
  };

  const { user, logout } = useAuth();

  const getInitials = (name: string): string => {
    return name
      .split(' ')                         // Split by spaces
      .filter(Boolean)                    // Remove empty parts
      .map(part => part[0].toUpperCase()) // Take first letter of each part and capitalize
      .join('');                          // Join into a string
  }

  return (
    <div 
      className={`${
        isCollapsed ? 'w-16' : 'w-56 min-w-[220px]'
      }  flex flex-col relative transition-all duration-300 bg-background-card overlay-elevation overlay-04 ${
        mobileOpen ? "absolute inset-y-0 left-0 z-50" : "hidden md:flex"
      }`}
    >
      {/* Logo & Brand */}
      <div className="px-4 py-6 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-md bg-gradient-to-r from-primary to-gray-500 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 12H7M17 12H21M12 3V7M12 17V21M5 19L8 16M16 8L19 5M19 19L16 16M5 5L8 8" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          {!isCollapsed && (
            <motion.span 
              initial={false}
              animate={{ opacity: isCollapsed ? 0 : 1 }}
              transition={{ duration: 0.2 }}
              className="font-heading font-bold text-xl text-white"
            >
              UnifAI
            </motion.span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {/* Collapse Toggle Button */}
          <button 
            className="text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-white hover:bg-opacity-10"
            onClick={toggleCollapse}
          >
            {isCollapsed ? <FaChevronRight size={14} /> : <FaChevronLeft size={14} />}
          </button>

          <button 
            className="md:hidden text-gray-400 hover:text-gray-800 dark:hover:text-white"
            onClick={() => setMobileOpen(false)}
          >
            <FaBars />
          </button>
        </div>
      </div>

      {/* Project Selector */}
      {/* <div className="px-4 py-3">
        <div className="bg-background-card rounded-md p-2 flex items-center justify-between cursor-pointer hover:bg-opacity-80 transition-all">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
              <span className="text-xs font-bold">{currentProject?.shortName || 'DP'}</span>
            </div>
            <span className="font-medium text-sm">{currentProject?.name || 'DataFlow Project'}</span>
          </div>
          <svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path>
          </svg>
        </div>
      </div> */}

      {/* Navigation Menu */}
      <nav className="mt-4 flex-grow">
        {!isCollapsed && (
          <motion.div 
            initial={false}
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            transition={{ duration: 0.2 }}
            className="px-3 mb-2"
          >
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">RAG</span>
          </motion.div>
        )}
        <ul>
          <NavItem 
            icon={<FaTachometerAlt className="sidebar-icon" />} 
            label="RAG Overview" 
            to="/rag-overview"
            isActive={location === '/rag-overview'}
            status={null}
            isCollapsed={isCollapsed}
            disabled={false}
          />
          <NavItem 
            icon={<FaSlack className="sidebar-icon" />} 
            label="Slack Integration" 
            to="/slack"
            isActive={location === '/slack'}
            status={null}
            isCollapsed={isCollapsed}
            disabled={true}
          />
          <NavItem 
            icon={<FaFileAlt className="sidebar-icon" />} 
            label="Documents" 
            to="/documents"
            isActive={location === '/documents'}
            status={null}
            isCollapsed={isCollapsed}
            disabled={false}
          />
        </ul>

        {!isCollapsed && (
          <motion.div 
            initial={false}
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            transition={{ duration: 0.2 }}
            className="px-3 mt-6 mb-2"
          >
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Agentic AI</span>
          </motion.div>
        )}
        <ul>
          <NavItem 
            icon={<FaTachometerAlt className="sidebar-icon" />} 
            label="Agentic AI Overview" 
            to="/agentic-overview"
            isActive={location === '/agentic-overview'}
            status={null}
            isCollapsed={isCollapsed}
          />
          <NavItem 
              icon={<FaFile className="sidebar-icon" />} 
              label="Agentic Inventory" 
              to="/inventory"
              isActive={location === '/inventory'}
              status={null}
              isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaRobot className="sidebar-icon" />} 
            label="Agentic AI Workflows" 
            to="/agentic-ai"
            isActive={location === '/agentic-ai'}
            status={null}
            // status="New"
            isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaComment className="sidebar-icon" />} 
            label="Agentic Chats" 
            to="/agentic-chats"
            isActive={location === '/agentic-chats'}
            status={null}
            isCollapsed={isCollapsed}
          />
        </ul>

        {!isCollapsed && (
          <motion.div 
            initial={false}
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            transition={{ duration: 0.2 }}
            className="px-3 mt-6 mb-2"
          >
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">System</span>
          </motion.div>
        )}
        <ul>
          <NavItem 
            icon={<FaInfoCircle className="sidebar-icon" />} 
            label="Getting Started" 
            to="/get-to-know"
            isActive={location === '/get-to-know'}
            status={null}
            isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaCogs className="sidebar-icon" />} 
            label="Configuration" 
            to="/configuration"
            isActive={location === '/configuration'}
            status={null}
            isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaBook className="sidebar-icon" />} 
            label="How-To Guides" 
            to="/guides"
            isActive={location === '/guides'}
            status={null}
            isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaChartLine className="sidebar-icon" />} 
            label="Analytics" 
            to="/analytics"
            isActive={location === '/analytics'}
            status={null}
            isCollapsed={isCollapsed}
            disabled={true}
          />
          <NavItem 
            icon={<FaUserShield className="sidebar-icon" />} 
            label="User Management" 
            to="/users"
            isActive={location === '/users'}
            status={null}
            isCollapsed={isCollapsed}
            disabled={true}
          />
          <NavItem 
            icon={<FaCog className="sidebar-icon" />} 
            label="Settings" 
            to="/settings"
            isActive={location === '/settings'}
            status={null}
            isCollapsed={isCollapsed}
            disabled={true}
          />
        </ul>
      </nav>

      {/* User Profile */}
      {/* <div className="px-4 py-3 border-t border-gray-800 mt-auto">
        <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'space-x-3'}`}>
          <div className="w-8 h-8 rounded-full bg-gradient-to-r from-accent to-primary flex items-center justify-center flex-shrink-0">
            <span className="text-sm font-medium text-white">{getInitials(user?.name || '')}</span>
          </div>
          {!isCollapsed && (
            <motion.div 
              initial={false}
              animate={{ opacity: isCollapsed ? 0 : 1 }}
              transition={{ duration: 0.2 }}
              className="flex-grow"
            >
              <h4 className="text-sm font-medium">{user?.name}</h4>
              <p className="text-xs text-gray-400">Administrator</p>
            </motion.div>
          )}
          {!isCollapsed && (
            <motion.div
              initial={false}
              animate={{ opacity: isCollapsed ? 0 : 1 }}
              transition={{ duration: 0.2 }}
            >
              <SimpleTooltip content={<p>Sign out</p>}>
                <button className="text-gray-400 hover:text-white">
                  <FaSignOutAlt />
                </button>
              </SimpleTooltip>
            </motion.div>
          )}
        </div>
      </div> */}
    </div>
  );
}

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  to: string;
  isActive: boolean;
  status: string | null;
  isCollapsed: boolean;
  disabled?: boolean;
}

function NavItem({ icon, label, to, isActive, status, isCollapsed, disabled = false }: NavItemProps) {
  const content = (
    <div 
      className={`flex items-center ${isCollapsed ? 'justify-center px-2' : 'justify-between px-4'} py-2.5 ${
        disabled
          ? "text-gray-600 opacity-50 cursor-not-allowed"
          : isActive 
            ? "text-white bg-primary bg-opacity-20 border-l-2 border-primary" 
            : "text-gray-400 hover:text-gray-800 dark:hover:text-white hover:bg-white hover:bg-opacity-5"
      } transition-all ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <div className={`flex items-center ${isCollapsed ? '' : 'space-x-3'}`}>
        {React.cloneElement(icon as React.ReactElement, { 
          className: `sidebar-icon ${disabled ? 'text-gray-600' : isActive ? 'text-secondary' : 'text-gray-400'}`
        })}
        {!isCollapsed && (
          <motion.span
            initial={false}
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            transition={{ duration: 0.2 }}
          >
            {label}
          </motion.span>
        )}
      </div>
      {!isCollapsed && status && (
        <motion.span 
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-xs py-0.5 px-2 rounded-full bg-success bg-opacity-20 text-success"
        >
          {status}
        </motion.span>
      )}
    </div>
  );

  if (disabled) {
    return (
      <li className="sidebar-item">
        {isCollapsed ? (
          <SimpleTooltip content={<p>{label} (Coming Soon)</p>}>
            {content}
          </SimpleTooltip>
        ) : (
          content
        )}
      </li>
    );
  }

  if (isCollapsed) {
    return (
      <li className="sidebar-item">
        <SimpleTooltip content={<p>{label}</p>}>
          <Link href={to}>
            {content}
          </Link>
        </SimpleTooltip>
      </li>
    );
  }

  return (
    <li className="sidebar-item">
      <Link href={to}>
        {content}
      </Link>
    </li>
  );
}