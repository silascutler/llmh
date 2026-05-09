type SearchBarProps = {
  action: string;
  name?: string;
  defaultValue?: string;
  placeholder: string;
  hiddenFields?: Record<string, string | string[]>;
};

export function SearchBar({ action, name = "q", defaultValue, placeholder, hiddenFields }: SearchBarProps) {
  return (
    <form action={action} className="cluster">
      {Object.entries(hiddenFields ?? {}).flatMap(([key, value]) => {
        const values = Array.isArray(value) ? value : [value];
        return values.map((item) => <input key={`${key}:${item}`} type="hidden" name={key} value={item} />);
      })}
      <input className="input mono" name={name} defaultValue={defaultValue} placeholder={placeholder} />
      <button className="ghost-button inline" type="submit">
        filter
      </button>
    </form>
  );
}
