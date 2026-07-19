import React from "react";

const OpenShellSandboxGuidelines: React.FC = () => (
  <details className="mt-3 text-sm text-gray-400 border border-gray-800 rounded-md">
    <summary className="cursor-pointer px-3 py-2 hover:text-gray-200 font-medium">
      Setup Guidelines
    </summary>
    <div className="px-3 pb-3 space-y-2">
      <p>
        OpenShell provides safe, sandboxed runtimes for autonomous AI agents.
      </p>
      <a
        href="https://github.com/NVIDIA/openshell"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline inline-flex items-center gap-1"
      >
        Repository & Documentation
      </a>
      <ul className="list-disc list-inside space-y-1 text-gray-500">
        <li>on your VM, deploy an OpenShell gateway and obtain mTLS certificates</li>
        <li>Upload CA cert, client cert, and client key in PEM format</li>
        <li>Gateway URL should be host:port (e.g. gateway.example.com:443)</li>
      </ul>
    </div>
  </details>
);

export default OpenShellSandboxGuidelines;
