package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	stduritemplate "github.com/std-uritemplate/std-uritemplate/go"
)

func main() {
	templateFile := os.Args[1]
	dataFile := os.Args[2]

	data, err := readJSONFile(dataFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "File '%s' not found.\n", dataFile)
		os.Exit(1)
	}

	val, ok := data["nativedate"]
	if ok {
		if f, ok := val.(float64); ok {
			data["nativedate"] = time.UnixMilli(int64(f))
		}
	}
	val2, ok := data["nativedatetwo"]
	if ok {
		if f2, ok := val2.(float64); ok {
			data["nativedatetwo"] = time.UnixMilli(int64(f2))
		}
	}
	val3, ok := data["nativedatethree"]
	if ok {
		if f3, ok := val3.(float64); ok {
			data["nativedatethree"] = time.UnixMilli(int64(f3) - 3600000).In(time.FixedZone("plus1", +1*60*60))
		}
	}
	val4, ok := data["nativedatefour"]
	if ok {
		if f4, ok := val4.(float64); ok {
			data["nativedatefour"] = time.UnixMilli(int64(f4) - 3600000).In(time.FixedZone("plus1", +1*60*60))
		}
	}

	template, err := readFile(templateFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "File '%s' not found.\n", templateFile)
		os.Exit(1)
	}

	result, err := stduritemplate.Expand(template, data)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error occurred: '%s'.\n", err)
		fmt.Print("false\n")
	} else {
		fmt.Print(result)
	}
}

func readFile(filename string) (string, error) {
	content, err := os.ReadFile(filename)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(content)), nil
}

func readJSONFile(filename string) (map[string]interface{}, error) {
	content, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}

	var data map[string]interface{}
	err = json.Unmarshal(content, &data)
	if err != nil {
		return nil, err
	}

	return data, nil
}
