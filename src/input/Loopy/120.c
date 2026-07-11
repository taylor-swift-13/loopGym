// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/05.c

extern int unknown1();
extern int unknown2();

void loopy_120(int flag)
{
	
	int x = 0;
	int y = 0;

	int j = 0;
	int i = 0;

	while(unknown2())
	{
	  x++;
	  y++;
	  i+=x;
	  j+=y;
	  if(flag)  j+=1;
	} 
	{;
//@ assert(j>=i);
}

}