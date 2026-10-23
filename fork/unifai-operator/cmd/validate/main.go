// Command validate applies the static rules of the UnifAI custom resources (internal/validate) to rendered
// manifests, e.g. `helm template ... | go run ./cmd/validate -`, before they reach a cluster. It prints each
// violation and exits 1 when there is any.
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"

	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/serializer"
	utilyaml "k8s.io/apimachinery/pkg/util/yaml"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/validate"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: validate FILE... (- for stdin)")
		os.Exit(2)
	}
	scheme := runtime.NewScheme()
	_ = unifaiv1.AddToScheme(scheme)
	decode := serializer.NewCodecFactory(scheme).UniversalDeserializer().Decode
	objects, violations := 0, 0
	for _, name := range os.Args[1:] {
		in := io.Reader(os.Stdin)
		if name != "-" {
			f, err := os.Open(name)
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(2)
			}
			defer func() { _ = f.Close() }()
			in = f
		}
		r := utilyaml.NewYAMLReader(bufio.NewReader(in))
		for {
			doc, err := r.Read()
			if errors.Is(err, io.EOF) {
				break
			}
			if err != nil {
				fmt.Fprintln(os.Stderr, name+":", err)
				os.Exit(2)
			}
			if len(bytes.TrimSpace(doc)) == 0 || !bytes.Contains(doc, []byte(unifaiv1.GroupVersion.Group)) {
				continue
			}
			for _, item := range items(doc) {
				obj, gvk, err := decode(item, nil, nil)
				if err != nil || gvk.Group != unifaiv1.GroupVersion.Group {
					continue // not one of ours
				}
				co, ok := obj.(client.Object)
				if !ok {
					continue
				}
				objects++
				for _, v := range validate.Check(co) {
					violations++
					fmt.Printf("%s %s/%s: %s\n", gvk.Kind, co.GetNamespace(), co.GetName(), v)
				}
			}
		}
	}
	fmt.Fprintf(os.Stderr, "%d UnifAI objects, %d violations\n", objects, violations)
	if violations > 0 {
		os.Exit(1)
	}
}

// items returns the objects of a document: the items of a List (kubectl get -o yaml), or the document itself.
func items(doc []byte) [][]byte {
	var list struct {
		Kind  string            `json:"kind"`
		Items []json.RawMessage `json:"items"`
	}
	js, err := utilyaml.ToJSON(doc)
	if err != nil || json.Unmarshal(js, &list) != nil || list.Kind != "List" {
		return [][]byte{doc}
	}
	out := make([][]byte, 0, len(list.Items))
	for _, it := range list.Items {
		out = append(out, it)
	}
	return out
}
