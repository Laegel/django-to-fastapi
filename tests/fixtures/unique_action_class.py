class UniqueActionView(APIView):
    def post(self):
        self.other_method("bla")

    def other_method(self, arg):
        ...
