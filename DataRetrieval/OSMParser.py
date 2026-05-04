class OSMParser:
    @staticmethod
    def build_node_index(data):
        return {
            el["id"]: (el["lon"], el["lat"])
            for el in data["elements"]
            if el["type"] == "node"
        }