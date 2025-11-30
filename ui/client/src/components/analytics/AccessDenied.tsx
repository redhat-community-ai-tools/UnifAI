import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FaLock } from "react-icons/fa";
import { useLocation } from "wouter";

export function AccessDenied() {
  const [, setLocation] = useLocation();

  return (
    <div className="p-6 flex items-center justify-center h-full">
      <Card className="bg-background-card shadow-card border-gray-800 p-8 max-w-md">
        <div className="text-center">
          <div className="mx-auto w-16 h-16 rounded-full bg-warning bg-opacity-20 flex items-center justify-center mb-4">
            <FaLock className="text-4xl text-warning" />
          </div>
          <h3 className="text-xl font-heading font-semibold mb-2">Access Restricted</h3>
          <p className="text-sm text-gray-400 mb-6">
            You don't have permission to access Analytics. Please contact your administrator if you need access.
          </p>
          <Button 
            onClick={() => setLocation('/agentic-ai')} 
            className="bg-primary hover:bg-opacity-80"
          >
            Go to Home
          </Button>
        </div>
      </Card>
    </div>
  );
}

