class UniqueActionView(APIView):
    def post(self, arg):
        ...

    def other_method(self):
        self.post("bla")
