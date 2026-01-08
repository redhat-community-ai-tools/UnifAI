import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import AITransparencyModal from '@/components/auth/AITransparencyModal';
import { checkUserApproval } from '@/api/termsApproval';

interface TermsApprovalProps {
  children: React.ReactNode;
}

/**
 * Component that ensures users have approved the terms/conditions
 * before accessing the application. Renders the AITransparencyModal
 * when approval is needed.
 */
const TermsApproval: React.FC<TermsApprovalProps> = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const [showModal, setShowModal] = useState(false);
  const [isCheckingApproval, setIsCheckingApproval] = useState(false);

  // Check approval status when user is authenticated
  useEffect(() => {
    if (isAuthenticated && user) {
      checkUserApprovalStatus(user.username);
    }
  }, [isAuthenticated, user]);

  const checkUserApprovalStatus = async (username: string) => {
    if (!username) return;
    
    // Check sessionStorage first - if user accepted in this session, don't show modal
    const sessionKey = `ai_transparency_accepted_${username}`;
    const sessionAccepted = sessionStorage.getItem(sessionKey);
    if (sessionAccepted === 'true') {
      // User already accepted in this session, don't show modal
      return;
    }
    
    setIsCheckingApproval(true);
    try {
      const approvalStatus = await checkUserApproval(username);
      
      if (!approvalStatus.approved) {
        setShowModal(true);
      } else {
        setShowModal(false);
      }
    } catch (error) {
      // If check fails, show modal to be safe
      setShowModal(true);
    } finally {
      setIsCheckingApproval(false);
    }
  };

  const handleApproved = async (dontShowAgain: boolean) => {
    setShowModal(false);
    
    if (user) {
      const sessionKey = `ai_transparency_accepted_${user.username}`;
      
      if (dontShowAgain) {
        // User checked "don't show again" - saved to database
        // Also save to sessionStorage as backup
        sessionStorage.setItem(sessionKey, 'true');
        
        // Verify the approval was saved to database
        try {
          const approvalStatus = await checkUserApproval(user.username);
          if (!approvalStatus.approved) {
            console.warn("User approval was not saved properly");
          }
        } catch (error) {
          console.error("Failed to verify user approval:", error);
        }
      } else {
        // User just accepted without "don't show again"
        // Save to sessionStorage so it doesn't show again in this session
        sessionStorage.setItem(sessionKey, 'true');
      }
    }
  };

  return (
    <>
      {children}
      {user && showModal && (
        <AITransparencyModal
          open={showModal}
          onClose={() => setShowModal(false)}
          username={user.username}
          onApproved={handleApproved}
        />
      )}
    </>
  );
};

export default TermsApproval;

