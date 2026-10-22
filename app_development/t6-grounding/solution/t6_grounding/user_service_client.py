from t6_grounding.grounding import UserService


class UserServiceClient(UserService):
    def get_all_users(self):
        return self.all()

    async def get_user(self, user_id):
        return self.user(user_id)

    def search_users(self, name=None, surname=None, email=None):
        return self.search(
            {
                key: value
                for key, value in {
                    "name": name,
                    "surname": surname,
                    "email": email,
                }.items()
                if value
            }
        )

    def health(self):
        return self.get("/health")
