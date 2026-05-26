import React from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/contexts/AuthContext';
import { useTheme } from '@/contexts/ThemeContext';
import { generateColorPalette } from '@/lib/colorUtils';
import { FaBuilding } from 'react-icons/fa';
import { HiSparkles } from 'react-icons/hi';

export default function Login() {
  const { login, isLoading: authLoading } = useAuth();
  const { primaryHex } = useTheme();
  const [primary, secondary] = generateColorPalette(primaryHex || "#A60000", 2);

  const handleSSOLogin = () => {
    login();
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-[#0D1117] via-[#161B22] to-[#1a1f2e]">
        <div className="absolute inset-0 opacity-30">
          <div
            className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full blur-3xl animate-pulse"
            style={{ backgroundColor: `${primary}33` }}
          />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse delay-1000" />
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10"
      >
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{
              background: `linear-gradient(135deg, ${primary}, ${secondary})`,
            }}
          >
            <HiSparkles className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="text-3xl font-bold text-white mb-2">Welcome to UnifAI</h1>
          <p className="text-gray-400">Sign in to continue to your dashboard</p>
        </div>

        <div className="w-full">
          <Button
            type="button"
            variant="secondary"
            className="w-full h-12 border-0 bg-[#21262d] text-white shadow-none hover:bg-[#30363d]"
            onClick={handleSSOLogin}
            disabled={authLoading}
          >
            <FaBuilding className="mr-2 h-4 w-4 shrink-0 opacity-80" />
            Login using SSO
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
