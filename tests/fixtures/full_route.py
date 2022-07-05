def create_post(request):
    title = request.data.get("title")
    content = request.data.get("content", "")
    blo = request.query_params["blo"]
    bli = request.query_params.get("bli")
    cat = request.query_params.get("category", "")
    if request.data.get("boolean_value") is not None:
        if request.data.get("boolean_value") == "":
            boolean_value = None
        else:
            boolean_value = request.data.get("boolean_value")
    items = do_this({
        **get_from(("stuff1", "stuff2"), request.data),
        "stuff3": "...",
    })
    other_items = request.data["other_items"] if cat == 12 else []
    
    return Response({
        "title": title,
        "content": content,
        "category": cat,
        "blo": blo,
        "bli": bli,
    })
