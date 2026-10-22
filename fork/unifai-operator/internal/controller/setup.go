package controller

import (
	"fmt"

	ctrl "sigs.k8s.io/controller-runtime"
)

// SetupAll registers every controller of the operator.
func SetupAll(mgr ctrl.Manager) error {
	base := Base{Client: mgr.GetClient(), Scheme: mgr.GetScheme(), APIReader: mgr.GetAPIReader(), Recorder: mgr.GetEventRecorder(EventSource)}
	for kind, newObj := range ResourceKinds {
		if err := (&ResourceReconciler{Base: base, Kind: kind, NewObj: newObj}).SetupWithManager(mgr); err != nil {
			return fmt.Errorf("%s: %w", kind, err)
		}
	}
	type setup interface{ SetupWithManager(ctrl.Manager) error }
	for name, r := range map[string]setup{
		"UnifaiWorkflow":    &WorkflowReconciler{Base: base},
		"UnifaiSchedule":    &ScheduleReconciler{Base: base},
		"UnifaiTemplate":    &TemplateReconciler{Base: base},
		"UnifaiChat":        &ChatReconciler{Base: base},
		"UnifaiRAGPipeline": &RAGPipelineReconciler{Base: base},
		"UnifaiRAGSource":   &RAGSourceReconciler{Base: base},
		"UnifaiAgentBundle": &AgentBundleReconciler{Client: mgr.GetClient(), Scheme: mgr.GetScheme()},
		"UnifaiStack":       NewStackReconciler(mgr),
	} {
		if err := r.SetupWithManager(mgr); err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
	}
	return nil
}
