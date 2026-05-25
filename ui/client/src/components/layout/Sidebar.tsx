import React from "react";
import { Link, useLocation } from "wouter";
import { useProject } from "@/contexts/ProjectContext";
import { 
  FaTachometerAlt, FaCogs, FaFileAlt, 
  FaChartLine, FaUserShield, FaCog, FaSignOutAlt,
  FaRobot, FaFile, FaChevronLeft, FaChevronRight,
  FaInfoCircle, FaBook, FaComment, FaPuzzlePiece,
} from "react-icons/fa";
import { FaSlack, FaBars } from "react-icons/fa";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import SimpleTooltip from "@/components/shared/SimpleTooltip";
import { useAuth, User } from '@/contexts/AuthContext';
import { useView, TeamInfo } from '@/contexts/ViewContext';
import { getEffectiveMemberCount } from '@/api/teams';
import { useAdminAccess } from '@/hooks/use-admin-access';
import { Users, ChevronDown, User as UserIcon, Settings, Plus, Loader2 } from "lucide-react";
import TeamSettingsModal from "@/components/teams/TeamSettingsModal";

export default function Sidebar() {
  const [location] = useLocation();
  const { currentProject } = useProject();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [teamDropdownOpen, setTeamDropdownOpen] = useState(false);

  const toggleCollapse = () => {
    setIsCollapsed(!isCollapsed);
  };

  const { user, logout } = useAuth();
  const { viewMode, setViewMode, selectedTeam, setSelectedTeam, teams, teamsLoading } = useView();
  const { isAdmin } = useAdminAccess();
  const [teamModalOpen, setTeamModalOpen] = useState(false);
  const [teamModalTarget, setTeamModalTarget] = useState<TeamInfo | null>(null);

  const openTeamSettings = (team: TeamInfo, e: React.MouseEvent) => {
    e.stopPropagation();
    setTeamModalTarget(team);
    setTeamModalOpen(true);
    setTeamDropdownOpen(false);
  };

  const openCreateTeam = () => {
    setTeamModalTarget(null);
    setTeamModalOpen(true);
    setTeamDropdownOpen(false);
  };

  const getInitials = (name: string): string => {
    return name
      .split(' ')
      .filter(Boolean)
      .map(part => part[0].toUpperCase())
      .join('');
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

      {/* View Switcher */}
      <div className={`${isCollapsed ? 'px-2' : 'px-3'} mt-2 mb-2`}>
        {isCollapsed ? (
          <SimpleTooltip content={<p>{viewMode === 'private' ? 'My Workspace' : (selectedTeam?.name ?? 'Team')}</p>}>
            <button
              onClick={() => setViewMode(viewMode === 'private' ? 'team' : 'private')}
              className={`w-full flex items-center justify-center py-2 rounded-lg transition-colors ${
                viewMode === 'team'
                  ? 'bg-primary/15 text-primary'
                  : 'bg-background-card text-gray-400 hover:text-white'
              }`}
            >
              {viewMode === 'private' ? <UserIcon className="w-4 h-4" /> : <Users className="w-4 h-4" />}
            </button>
          </SimpleTooltip>
        ) : (
          <div className="relative">
            <div className="flex bg-background-card border border-gray-800 rounded-lg p-0.5 gap-0.5">
              <button
                onClick={() => setViewMode('private')}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  viewMode === 'private'
                    ? 'bg-primary/15 text-primary'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <UserIcon className="w-3 h-3" />
                Personal
              </button>
              <button
                onClick={() => { setViewMode('team'); }}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  viewMode === 'team'
                    ? 'bg-primary/15 text-primary'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <Users className="w-3 h-3" />
                Team
              </button>
            </div>

            {/* Team selector dropdown (only visible in team mode) */}
            <AnimatePresence>
              {viewMode === 'team' && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <button
                    onClick={() => setTeamDropdownOpen(!teamDropdownOpen)}
                    className="w-full mt-1.5 flex items-center justify-between px-2.5 py-1.5 rounded-lg border border-gray-800 bg-background-card hover:border-gray-700 transition-colors"
                  >
                    <span className="text-xs font-medium text-white truncate">
                      {teamsLoading && !selectedTeam ? 'Loading teams…' : (selectedTeam?.name ?? 'Select team')}
                    </span>
                    <ChevronDown className={`w-3 h-3 text-gray-500 transition-transform flex-shrink-0 ${teamDropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  <AnimatePresence>
                    {teamDropdownOpen && (
                      <>
                        <div className="fixed inset-0 z-40" onClick={() => setTeamDropdownOpen(false)} />
                        <motion.div
                          initial={{ opacity: 0, y: -4 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -4 }}
                          transition={{ duration: 0.15 }}
                          className="absolute left-0 right-0 mt-1 bg-[#1a1a2e] border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden"
                        >
                          <div className="p-1.5">
                            {teamsLoading ? (
                              <div className="flex items-center gap-2 px-3 py-3 text-xs text-gray-500">
                                <Loader2 className="w-3 h-3 animate-spin" />
                                Loading teams…
                              </div>
                            ) : teams.length === 0 ? (
                              <div className="px-3 py-3 text-xs text-gray-600 text-center">
                                No teams yet
                              </div>
                            ) : (
                              teams.map((team) => {
                                const count = getEffectiveMemberCount(team.members, team.effective_member_count);
                                return (
                                  <div
                                    key={team.id}
                                    className={`flex items-center gap-1 rounded-lg transition-colors ${
                                      selectedTeam?.id === team.id ? 'bg-primary/10' : 'hover:bg-white/[.03]'
                                    }`}
                                  >
                                    <button
                                      onClick={() => { setSelectedTeam(team); setTeamDropdownOpen(false); }}
                                      className="flex-1 flex items-center gap-2 px-2 py-1.5 text-left min-w-0"
                                    >
                                      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${selectedTeam?.id === team.id ? 'bg-primary' : 'bg-gray-700'}`} />
                                      <div className="flex-1 min-w-0">
                                        <div className={`text-xs font-semibold truncate ${selectedTeam?.id === team.id ? 'text-primary' : 'text-gray-300'}`}>{team.name}</div>
                                        <div className="text-[10px] text-gray-600">{count} member{count !== 1 ? 's' : ''}</div>
                                      </div>
                                    </button>
                                    <button
                                      onClick={(e) => openTeamSettings(team, e)}
                                      className="p-1 rounded-md text-gray-600 hover:text-gray-300 hover:bg-white/5 transition-colors flex-shrink-0 mr-1"
                                    >
                                      <Settings className="w-3 h-3" />
                                    </button>
                                  </div>
                                );
                              })
                            )}
                          </div>
                          <div className="border-t border-gray-700/50">
                            <button
                              onClick={openCreateTeam}
                              className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs font-medium text-primary/80 hover:text-primary hover:bg-primary/5 transition-colors"
                            >
                              <Plus className="w-3.5 h-3.5" />
                              Create a new team
                            </button>
                          </div>
                        </motion.div>
                      </>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Navigation Menu */}
      <nav className="mt-2 flex-grow">
        {!isCollapsed && (
          <motion.div 
            initial={false}
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            transition={{ duration: 0.2 }}
            className="px-3 mb-2"
          >
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Agentic AI
            </span>
          </motion.div>
        )}
        <ul>
          <NavItem 
            icon={<FaTachometerAlt className="sidebar-icon" />} 
            label={viewMode === 'team' ? 'Team Dashboard' : 'Agentic AI Overview'}
            to="/agentic-overview"
            isActive={location === '/agentic-overview'}
            status={null}
            isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaPuzzlePiece className="sidebar-icon" />} 
            label="Agentic AI Templates" 
            to="/templates"
            isActive={location === '/templates'}
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
            isCollapsed={isCollapsed}
          />
          <NavItem 
            icon={<FaComment className="sidebar-icon" />} 
            label={viewMode === 'team' ? 'Collaboration Hub' : 'Agentic Chats'}
            to="/agentic-chats"
            isActive={location === '/agentic-chats'}
            status={null}
            isCollapsed={isCollapsed}
          />
        </ul>
        
        {viewMode !== 'team' && (
          <>
            {!isCollapsed && (
              <motion.div 
                initial={false}
                animate={{ opacity: isCollapsed ? 0 : 1 }}
                transition={{ duration: 0.2 }}
                className="px-3 mt-6 mb-2"
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
          </>
        )}


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
            icon={<FaBook className="sidebar-icon" />} 
            label="How-To Guides" 
            to="/guides"
            isActive={location === '/guides'}
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
            disabled={!isAdmin}
          />
          {user?.is_admin && (
          <NavItem 
            icon={<FaChartLine className="sidebar-icon" />} 
            label="Analytics" 
            to="/analytics"
            isActive={location === '/analytics'}
            status={null}
            isCollapsed={isCollapsed}
          />
          )}
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

      <TeamSettingsModal
        open={teamModalOpen}
        onOpenChange={setTeamModalOpen}
        team={teamModalTarget}
      />
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
