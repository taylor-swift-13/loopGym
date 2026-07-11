// Source: data/benchmarks/sv-benchmarks/loop-simple/nested_1.c

void loopy_388(void) {
	int a = 6;

	{
  a = 0;
  while (a < 6) {
    ++a;
  }
}
	if(!(a == 6 )) {
		{; 
//@ assert(\false);
};
	}
	return;
}