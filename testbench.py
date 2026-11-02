# Uncomment the next line to test on PC without access to the Inky modules
import inky_stubs
import main
if __name__ == "__main__":
    url = "https://drive.google.com/uc?export=view&id=1l2uFHRm2DAGHa_5Co64g__itNZMcwwbs"
    json_body = main.load_json_body(url)
    main.process_json_body(json_body)
