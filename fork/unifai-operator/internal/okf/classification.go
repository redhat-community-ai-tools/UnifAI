package okf

import "fmt"

// Level is a Zuno data classification (ADR-0021): C1 public < C2 internal < C3 restricted (local models only).
type Level int

const (
	C1 Level = iota + 1
	C2
	C3
)

func (l Level) String() string {
	switch l {
	case C1:
		return "C1"
	case C2:
		return "C2"
	case C3:
		return "C3"
	}
	return fmt.Sprintf("Level(%d)", int(l))
}

// ParseLevel accepts C1, C2 or C3.
func ParseLevel(s string) (Level, error) {
	switch s {
	case "C1":
		return C1, nil
	case "C2":
		return C2, nil
	case "C3":
		return C3, nil
	}
	return 0, fmt.Errorf("unknown classification %q (want C1, C2 or C3)", s)
}

// Effective applies an override to a default classification. An override may only raise the level
// (ADR-0565): lowering it would let restricted context reach a model class the bundle forbids.
func Effective(def Level, override string) (Level, error) {
	if override == "" {
		return def, nil
	}
	o, err := ParseLevel(override)
	if err != nil {
		return 0, err
	}
	if o < def {
		return 0, fmt.Errorf("override %s would lower the bundle's classification %s; only raising is allowed", o, def)
	}
	return o, nil
}
