export type AuthFormState = {
  error: string | null;
  notice: string | null;
};

export const initialAuthFormState: AuthFormState = {
  error: null,
  notice: null
};
